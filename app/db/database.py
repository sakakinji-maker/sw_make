"""SQLite 연결과 세션을 관리한다."""

from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """모든 모델의 부모 클래스."""


def create_tables() -> None:
    """모델 정의를 바탕으로 테이블만 만든다. 가상 데이터 적재(seed)는 이것만 쓴다."""
    from app.models import models  # noqa: F401  (모델 등록용 import)

    Base.metadata.create_all(bind=engine)
    add_missing_columns()


# 나중에 추가한 칸 (테이블, 칸, SQL 타입). create_all은 있는 테이블에 칸을 더하지 않는다.
ADDED_COLUMNS = [("reservation_histories", "memo", "VARCHAR(100)")]


def add_missing_columns() -> None:
    """예전 DB(app.db, Railway)에 새 칸이 없으면 추가한다. 이미 있으면 아무것도 안 한다."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, column, sql_type in ADDED_COLUMNS:
            if not inspector.has_table(table):
                continue
            if column not in {c["name"] for c in inspector.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))


def init_db() -> None:
    """테이블을 만든다."""
    from app.models import models  # noqa: F401

    create_tables()


def get_session() -> Iterator[Session]:
    """FastAPI 의존성 주입용 세션."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
