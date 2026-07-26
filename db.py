"""정산 데이터 영구 저장소.

DATABASE_URL 환경변수가 있으면 그 Postgres에, 없으면 로컬 settlement.db(SQLite)에
저장한다. 정산일(settlement_date) 하루 = 배치 하나로 저장하고, 같은 날짜가 다시
업로드되면 기존 배치를 덮어쓴다(재업로드로 값을 고칠 수 있도록). 여러 날짜를
누적 저장하므로 기간별 조회, 라이더별 누적 이력 조회가 가능하다.
"""

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Column, Float, ForeignKey, Integer, MetaData, String, Table,
    create_engine, delete, func, insert, inspect, select, text, update,
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
    Column("settlement_date", String, nullable=False, unique=True),
    Column("coupang_filename", String),
    Column("baemin_filename", String),
    Column("uploaded_at", String, nullable=False),
)

settlement_records = Table(
    "settlement_records", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("batch_id", Integer, ForeignKey("settlement_batches.id"), nullable=False),
    Column("name", String),
    Column("platforms", String),  # "coupang", "baemin", "coupang,baemin"
    *[Column(f, Float) for f in RECORD_FIELDS if f != "name"],
)


def init_db():
    metadata.create_all(engine)
    # settlement_date에 UNIQUE 제약이 없던 구버전 DB, platforms 컬럼이 없던 구버전 DB 보정
    inspector = inspect(engine)
    existing_cols = {c["name"] for c in inspector.get_columns("settlement_records")}
    if "platforms" not in existing_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE settlement_records ADD COLUMN platforms VARCHAR"))


def _find_batch_id(conn, settlement_date: str):
    return conn.execute(
        select(settlement_batches.c.id)
        .where(settlement_batches.c.settlement_date == settlement_date)
    ).scalar()


def save_batch(records: list[dict], settlement_date: str,
               coupang_filename: str, baemin_filename: str,
               uploaded_at: str | None = None) -> int:
    """정산일 하나에 대한 배치를 저장(이미 있으면 덮어씀)하고 batch_id를 반환한다."""
    uploaded_at = uploaded_at or datetime.now().isoformat(timespec="seconds")
    with engine.begin() as conn:
        batch_id = _find_batch_id(conn, settlement_date)
        if batch_id is not None:
            conn.execute(
                delete(settlement_records).where(settlement_records.c.batch_id == batch_id)
            )
            conn.execute(
                update(settlement_batches)
                .where(settlement_batches.c.id == batch_id)
                .values(coupang_filename=coupang_filename, baemin_filename=baemin_filename,
                        uploaded_at=uploaded_at)
            )
        else:
            result = conn.execute(
                insert(settlement_batches).values(
                    settlement_date=settlement_date,
                    coupang_filename=coupang_filename,
                    baemin_filename=baemin_filename,
                    uploaded_at=uploaded_at,
                )
            )
            batch_id = result.inserted_primary_key[0]

        rows = [
            {
                "batch_id": batch_id,
                "platforms": r.get("platforms", ""),
                **{f: r.get(f, 0) for f in RECORD_FIELDS},
            }
            for r in records
        ]
        if rows:
            conn.execute(insert(settlement_records), rows)
        return batch_id


def load_latest_batch() -> tuple[list[dict], dict] | None:
    """가장 최근 정산일 배치의 (레코드 목록, 배치 메타정보)를 반환. 없으면 None."""
    with engine.begin() as conn:
        batch = conn.execute(
            select(settlement_batches)
            .order_by(settlement_batches.c.settlement_date.desc())
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


def load_date_bounds() -> tuple[str, str] | None:
    """지금까지 저장된 배치들의 (가장 이른 정산일, 가장 최근 정산일). 없으면 None."""
    with engine.begin() as conn:
        row = conn.execute(
            select(func.min(settlement_batches.c.settlement_date),
                   func.max(settlement_batches.c.settlement_date))
        ).first()
        if row is None or row[0] is None:
            return None
        return row[0], row[1]


def load_batches_in_range(start_date: str, end_date: str) -> list[dict]:
    """기간 내(양끝 포함) 배치 메타정보 목록을 날짜순으로 반환."""
    with engine.begin() as conn:
        rows = conn.execute(
            select(settlement_batches)
            .where(settlement_batches.c.settlement_date >= start_date)
            .where(settlement_batches.c.settlement_date <= end_date)
            .order_by(settlement_batches.c.settlement_date)
        ).mappings().all()
        return [dict(r) for r in rows]


def load_records_in_range(start_date: str, end_date: str) -> list[dict]:
    """기간 내 모든 라이더별 레코드를 정산일과 함께 반환 (일별/기간별 집계용)."""
    with engine.begin() as conn:
        rows = conn.execute(
            select(settlement_records, settlement_batches.c.settlement_date)
            .join(settlement_batches, settlement_records.c.batch_id == settlement_batches.c.id)
            .where(settlement_batches.c.settlement_date >= start_date)
            .where(settlement_batches.c.settlement_date <= end_date)
        ).mappings().all()
        out = []
        for row in rows:
            rec = {f: (row[f] or 0) for f in RECORD_FIELDS}
            rec["name"] = row["name"]
            rec["platforms"] = row["platforms"] or ""
            rec["settlement_date"] = row["settlement_date"]
            out.append(rec)
        return out


def load_all_rider_history() -> list[dict]:
    """지금까지 업로드된 모든 정산일을 통틀어 라이더별 누적 통계를 반환."""
    with engine.begin() as conn:
        rows = conn.execute(
            select(settlement_records, settlement_batches.c.settlement_date)
            .join(settlement_batches, settlement_records.c.batch_id == settlement_batches.c.id)
        ).mappings().all()

    agg: dict[str, dict] = {}
    for row in rows:
        name = row["name"]
        d = agg.setdefault(name, {
            "name": name, "orders": 0.0, "gross": 0.0, "final": 0.0,
            "active_days": 0, "first_date": row["settlement_date"],
            "last_date": row["settlement_date"], "platforms": set(),
        })
        d["orders"] += row["orders"] or 0
        d["gross"] += row["gross"] or 0
        d["final"] += row["final"] or 0
        d["active_days"] += 1
        d["first_date"] = min(d["first_date"], row["settlement_date"])
        d["last_date"] = max(d["last_date"], row["settlement_date"])
        if row["platforms"]:
            d["platforms"].update(row["platforms"].split(","))

    result = []
    for d in agg.values():
        d["platforms"] = ", ".join(sorted(d["platforms"])) if d["platforms"] else "-"
        result.append(d)
    return sorted(result, key=lambda r: -r["gross"])


init_db()
