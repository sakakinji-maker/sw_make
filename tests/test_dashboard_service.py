# AI-assisted (ChatGPT) — 전지호 검토 필요
"""F-05 대시보드 서비스 테스트."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.dashboard import service as dashboard_service


def test_dashboard_service_filters_and_counts(monkeypatch):
    """오늘 이후 요청·확정만 시간순으로 남기고 나머지 현황을 전달한다."""
    now = datetime(2026, 11, 17, 9, 0)
    reservations = [
        SimpleNamespace(reserved_at=datetime(2026, 11, 18, 12), status="확정"),
        SimpleNamespace(reserved_at=datetime(2026, 11, 17, 8), status="요청"),
        SimpleNamespace(reserved_at=datetime(2026, 11, 19, 12), status="취소"),
        SimpleNamespace(reserved_at=datetime(2026, 11, 16, 12), status="요청"),
        SimpleNamespace(reserved_at=datetime(2026, 11, 20, 12), status="요청"),
    ]
    reservation_service = Mock()
    reservation_service.list_for_store.return_value = reservations
    inquiry_repository = Mock()
    inquiry_repository.count_unanswered_by_store.return_value = 3
    contents = [SimpleNamespace(text="최근 콘텐츠")]

    monkeypatch.setattr(dashboard_service, "ReservationService", lambda session: reservation_service)
    monkeypatch.setattr(dashboard_service, "InquiryRepository", lambda session: inquiry_repository)
    monkeypatch.setattr(dashboard_service, "count_marketing_contents", lambda session, store_id: 6)
    monkeypatch.setattr(
        dashboard_service,
        "list_marketing_contents",
        lambda session, store_id, limit: contents if limit == 5 else [],
    )

    result = dashboard_service.DashboardService(Mock(), now=lambda: now).get_dashboard(1)

    assert [item.reserved_at for item in result.reservations] == [
        datetime(2026, 11, 17, 8),
        datetime(2026, 11, 18, 12),
        datetime(2026, 11, 20, 12),
    ]
    assert result.status_counts == {"요청": 2, "확정": 1}
    assert result.unanswered == 3
    assert result.contents_count == 6
    assert result.contents == contents
    reservation_service.list_for_store.assert_called_once_with(1)
    inquiry_repository.count_unanswered_by_store.assert_called_once_with(1)
