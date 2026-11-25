# AI-assisted (Claude)
"""제출용 데이터베이스 산출물을 docs/database/에 만든다 (14주차 최종 산출물).

실행:
    python -m scripts.export_database

만드는 파일:
    schema.sql       모델(app/models/models.py)에서 뽑은 CREATE TABLE 문
    sample_data.sql  가상 데이터(app/db/seed_data/*.json)를 넣은 INSERT 문
    sample.db        위 두 가지가 들어 있는 SQLite 파일 (DB Browser for SQLite 등으로 열람)

app/db/app.db(개발용 DB)는 건드리지 않는다. 모델이나 가상 데이터를 바꾸면 다시 실행한다.
"""

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

import app.models.models  # noqa: F401 - 테이블을 Base.metadata에 등록한다
from app.db.database import Base
from app.db.seed import load_all

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "database"
HEADER = (
    "-- 브루밍 카페 예약·문의·홍보 시스템 데이터베이스 (SQLite)\n"
    "-- 자동 생성: python -m scripts.export_database\n"
    "-- 직접 고치지 말고 모델·가상 데이터를 고친 뒤 다시 생성한다.\n"
)


def schema_sql() -> str:
    """모델 기준 CREATE TABLE 문. 외래키가 있는 테이블은 참조 대상 뒤에 나온다."""
    engine = create_engine("sqlite://")
    tables = [
        str(CreateTable(t).compile(engine)).strip() + ";" for t in Base.metadata.sorted_tables
    ]
    return HEADER + f"-- 테이블 {len(tables)}개\n\n" + "\n\n".join(tables) + "\n"


def build_sample_db(path: Path) -> None:
    """가상 데이터를 넣은 SQLite 파일을 새로 만든다."""
    path.unlink(missing_ok=True)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        load_all(session)
        session.commit()
    engine.dispose()


def sample_data_sql(db_path: Path) -> str:
    """sample.db의 데이터를 INSERT 문으로 (테이블 생성 문은 schema.sql에 있으므로 뺀다)."""
    with sqlite3.connect(db_path) as conn:
        inserts = [line for line in conn.iterdump() if line.startswith("INSERT INTO")]
    return (
        HEADER
        + f"-- INSERT {len(inserts)}건\n\nBEGIN TRANSACTION;\n"
        + "\n".join(inserts)
        + "\nCOMMIT;\n"
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "schema.sql").write_text(schema_sql(), encoding="utf-8")
    db_path = OUT_DIR / "sample.db"
    build_sample_db(db_path)
    (OUT_DIR / "sample_data.sql").write_text(sample_data_sql(db_path), encoding="utf-8")
    print(f"만들었습니다: {OUT_DIR / 'schema.sql'}, sample_data.sql, sample.db")


if __name__ == "__main__":
    main()
