# AI-assisted (ChatGPT) — 전지호 검토 필요 / 11·24 오늘 예약·확정 대기 추가 (Claude, 한재형)
"""점주 대시보드에 필요한 현황을 조합한다 (F-05)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.models import MarketingContent, Reservation, Store
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
    # F-05-1 '오늘 예약 목록(상태별)': 오늘 날짜의 모든 예약과 상태별 건수
    today_reservations: list[Reservation] = field(default_factory=list)
    today_counts: dict[str, int] = field(default_factory=dict)
    pending: int = 0  # 점주가 확정해야 할 '요청' 예약 수 (오늘 이후)
    week: list[tuple[date, int]] = field(default_factory=list)  # 오늘부터 7일, 날짜별 예약 수
    open_time: time = time(9)
    close_time: time = time(21)


class DashboardService:
    def __init__(self, session: Session, now: Callable[[], datetime] = datetime.now) -> None:
        self.session = session
        self.reservations = ReservationService(session)
        self.inquiries = InquiryRepository(session)
        self.now = now

    def get_dashboard(self, store_id: int) -> DashboardData:
        """오늘 이후 요청·확정 예약과 문의·홍보 콘텐츠 현황을 계산한다."""
        today = self.now().date()
        all_reservations = self.reservations.list_for_store(store_id)
        reservations = [
            reservation
            for reservation in all_reservations
            if reservation.reserved_at.date() >= today and reservation.status in {"요청", "확정"}
        ]
        today_reservations = sorted(
            (r for r in all_reservations if r.reserved_at.date() == today),
            key=lambda r: r.reserved_at,
        )
        # 오늘부터 7일 동안 날짜별 예약 수 (취소·노쇼 제외) — 대시보드 막대그래프
        alive = [r for r in all_reservations if r.status not in {"취소", "노쇼"}]
        week = [
            (day, sum(r.reserved_at.date() == day for r in alive))
            for day in (today + timedelta(days=i) for i in range(7))
        ]
        store = self.session.get(Store, store_id)
        today_counts: dict[str, int] = {}
        for r in today_reservations:
            today_counts[r.status] = today_counts.get(r.status, 0) + 1
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
            today_reservations=today_reservations,
            today_counts=today_counts,
            pending=status_counts["요청"],
            week=week,
            open_time=store.open_time if store else time(9),
            close_time=store.close_time if store else time(21),
        )
