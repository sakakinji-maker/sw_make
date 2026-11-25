from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db import database
from app.models.models import Inquiry, Reservation, Store

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

STORE_ID = 1  # 단일 매장 시스템
DEFAULT_BRAND = "매장 안내"


def current_store() -> Store | None:
    """고객 화면 상단 이름·하단 매장 정보에 쓰는 매장. 점주가 정보를 바꾸면 바로 반영된다."""
    try:
        with database.SessionLocal() as session:
            store = session.get(Store, STORE_ID)
            if store is not None:
                session.expunge(store)  # 세션을 닫은 뒤에도 템플릿에서 읽을 수 있게
            return store
    except SQLAlchemyError:
        return None


def store_name() -> str:
    store = current_store()
    return store.name if store else DEFAULT_BRAND


def owner_counts() -> dict[str, int]:
    """점주 사이드바 숫자 배지: 확정 대기 예약(오늘 이후 '요청'), 미응답 문의."""
    today = datetime.combine(date.today(), datetime.min.time())
    try:
        with database.SessionLocal() as session:
            pending = session.scalar(
                select(func.count())
                .select_from(Reservation)
                .where(
                    Reservation.store_id == STORE_ID,
                    Reservation.status == "요청",
                    Reservation.reserved_at >= today,
                )
            )
            unanswered = session.scalar(
                select(func.count())
                .select_from(Inquiry)
                .where(Inquiry.store_id == STORE_ID, Inquiry.status == "미응답")
            )
            return {"pending": pending or 0, "unanswered": unanswered or 0}
    except SQLAlchemyError:
        return {"pending": 0, "unanswered": 0}


templates.env.globals["current_store"] = current_store
templates.env.globals["owner_counts"] = owner_counts
templates.env.globals["store_name"] = store_name
