# AI-assisted (ChatGPT) — 전지호 검토 필요
"""점주 대시보드에 필요한 현황을 조합한다 (F-05)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.models import MarketingContent, Reservation
from app.repositories.inquiry_repository import InquiryRepository
from app.repositories.marketing_repository import (
    count_marketing_contents,
    list_marketing_contents,
)
from app.services.reservation.service import ReservationService


@dataclass
class DashboardData:
    """대시보드 화면에 전달할 조회 결과."""

    today: date
    reservations: list[Reservation]
    status_counts: dict[str, int]
    unanswered: int
    contents_count: int
    contents: list[MarketingContent]


class DashboardService:
    def __init__(self, session: Session, now: Callable[[], datetime] = datetime.now) -> None:
        self.session = session
        self.reservations = ReservationService(session)
        self.inquiries = InquiryRepository(session)
        self.now = now

    def get_dashboard(self, store_id: int) -> DashboardData:
        """오늘 이후 요청·확정 예약과 문의·홍보 콘텐츠 현황을 계산한다."""
        today = self.now().date()
        reservations = [
            reservation
            for reservation in self.reservations.list_for_store(store_id)
            if reservation.reserved_at.date() >= today and reservation.status in {"요청", "확정"}
        ]
        reservations.sort(key=lambda reservation: reservation.reserved_at)
        status_counts = {
            "요청": sum(reservation.status == "요청" for reservation in reservations),
            "확정": sum(reservation.status == "확정" for reservation in reservations),
        }
        return DashboardData(
            today=today,
            reservations=reservations,
            status_counts=status_counts,
            unanswered=self.inquiries.count_unanswered_by_store(store_id),
            contents_count=count_marketing_contents(self.session, store_id),
            contents=list_marketing_contents(self.session, store_id, limit=5),
        )
