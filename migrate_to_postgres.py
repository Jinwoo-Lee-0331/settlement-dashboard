"""로컬 settlement.db(SQLite)의 데이터를 DATABASE_URL이 가리키는 Postgres로 옮긴다.

사용법:
    DATABASE_URL이 설정된 상태(.env 또는 환경변수)에서 실행하면
    로컬 settlement.db에 저장된 모든 정산 배치를 Postgres로 복사한다.
    일회성 스크립트이므로 실행 후 다시 쓸 필요는 없다.

    python migrate_to_postgres.py
"""

import sqlite3
from pathlib import Path

import db  # DATABASE_URL이 설정돼 있으면 여기서 Postgres 엔진으로 연결된다

LOCAL_DB_PATH = Path(__file__).parent / "settlement.db"


def main():
    if "sqlite" not in str(db.engine.url) or db.engine.url.database != str(LOCAL_DB_PATH):
        pass  # DATABASE_URL이 설정돼 있으면 db.engine은 이미 Postgres를 가리킴 (정상)
    else:
        print("DATABASE_URL이 설정되어 있지 않습니다. .env에 DATABASE_URL을 넣고 다시 실행하세요.")
        return

    if not LOCAL_DB_PATH.exists():
        print(f"로컬 DB 파일이 없습니다: {LOCAL_DB_PATH}")
        return

    src = sqlite3.connect(LOCAL_DB_PATH)
    src.row_factory = sqlite3.Row

    batches = src.execute("SELECT * FROM settlement_batches ORDER BY id").fetchall()
    if not batches:
        print("이관할 배치가 없습니다.")
        return

    for batch in batches:
        rows = src.execute(
            "SELECT * FROM settlement_records WHERE batch_id = ?", (batch["id"],)
        ).fetchall()
        records = [{f: row[f] for f in db.RECORD_FIELDS} for row in rows]
        new_id = db.save_batch(
            records,
            settlement_date=batch["settlement_date"],
            coupang_filename=batch["coupang_filename"],
            baemin_filename=batch["baemin_filename"],
            uploaded_at=batch["uploaded_at"],
        )
        print(f"배치 #{batch['id']} ({batch['settlement_date']}, {len(records)}명) "
              f"-> Postgres 배치 #{new_id}로 이관 완료")

    src.close()
    print("이관이 모두 끝났습니다.")


if __name__ == "__main__":
    main()
