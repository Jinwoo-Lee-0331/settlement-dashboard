"""정산 데이터 영구 저장소.

DATABASE_URL 환경변수가 있으면 그 Postgres에, 없으면 로컬 settlement.db(SQLite)에
저장한다. 업로드된 정산 데이터를 배치 단위로 저장해, 서버를 재시작하거나
(Render처럼) 재배포해도 마지막에 업로드한 데이터를 다시 볼 수 있게 한다.
"""

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Column, Float, ForeignKey, Integer, MetaData, String, Table,
    create_engine, insert, select,
)

load_dotenv()

RECORD_FIELDS = [
    "rider_id", "name", "orders", "gross", "employ_ins", "accident_ins",
    "hourly_ins", "ins_refund", "expected", "promo", "other_income",
    "commission", "withholding", "rental", "lease", "prepaid",
    "other_expense", "final",
]

_DATABASE_URL = os.environ.get("DATABASE_URL")
if _DATABASE_URL:
    # Neon/Render 등은 postgres://로 주기도 하는데 SQLAlchemy 2.x는 postgresql:// 필요
    if _DATABASE_URL.startswith("postgres://"):
        _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
else:
    _db_path = Path(__file__).parent / "settlement.db"
    engine = create_engine(f"sqlite:///{_db_path}")

metadata = MetaData()

settlement_batches = Table(
    "settlement_batches", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("settlement_date", String, nullable=False),
    Column("coupang_filename", String),
    Column("baemin_filename", String),
    Column("uploaded_at", String, nullable=False),
)

settlement_records = Table(
    "settlement_records", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("batch_id", Integer, ForeignKey("settlement_batches.id"), nullable=False),
    Column("name", String),
    *[Column(f, Float) for f in RECORD_FIELDS if f != "name"],
)


def init_db():
    metadata.create_all(engine)


def save_batch(records: list[dict], settlement_date: str,
               coupang_filename: str, baemin_filename: str,
               uploaded_at: str | None = None) -> int:
    """새 정산 배치를 저장하고 batch_id를 반환한다."""
    with engine.begin() as conn:
        result = conn.execute(
            insert(settlement_batches).values(
                settlement_date=settlement_date,
                coupang_filename=coupang_filename,
                baemin_filename=baemin_filename,
                uploaded_at=uploaded_at or datetime.now().isoformat(timespec="seconds"),
            )
        )
        batch_id = result.inserted_primary_key[0]
        rows = [
            {"batch_id": batch_id, **{f: r.get(f, 0) for f in RECORD_FIELDS}}
            for r in records
        ]
        if rows:
            conn.execute(insert(settlement_records), rows)
        return batch_id


def load_latest_batch() -> tuple[list[dict], dict] | None:
    """가장 최근에 업로드된 배치의 (레코드 목록, 배치 메타정보)를 반환. 없으면 None."""
    with engine.begin() as conn:
        batch = conn.execute(
            select(settlement_batches)
            .order_by(settlement_batches.c.id.desc())
            .limit(1)
        ).mappings().first()
        if batch is None:
            return None
        rows = conn.execute(
            select(settlement_records)
            .where(settlement_records.c.batch_id == batch["id"])
        ).mappings().all()
        records = [{f: row[f] for f in RECORD_FIELDS} for row in rows]
        meta = dict(batch)
        return records, meta


init_db()
