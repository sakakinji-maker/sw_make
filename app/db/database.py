"""SQLite 연결과 세션을 관리한다."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """모든 모델의 부모 클래스."""


def init_db() -> None:
    """모델 정의를 바탕으로 테이블을 만든다."""
    from app.models import models  # noqa: F401  (모델 등록용 import)

    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI 의존성 주입용 세션."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
