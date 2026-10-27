"""예약 State 패턴 테스트 (F-02-4): 정상 전이와 거부되는 전이."""

import pytest

from app.services.reservation.states import (
    InvalidTransitionError,
    ReservationStatus,
    state_of,
)


@pytest.mark.parametrize(
    ("start", "action", "expected"),
    [
        ("요청", "confirm", ReservationStatus.CONFIRMED),
        ("요청", "cancel", ReservationStatus.CANCELLED),
        ("요청", "change", ReservationStatus.REQUESTED),
        ("확정", "visit", ReservationStatus.VISITED),
        ("확정", "no_show", ReservationStatus.NO_SHOW),
        ("확정", "cancel", ReservationStatus.CANCELLED),
        ("확정", "change", ReservationStatus.REQUESTED),  # 변경 시 재확정 필요
    ],
)
def test_allowed_transitions(start, action, expected):
    assert getattr(state_of(start), action)().status == expected


@pytest.mark.parametrize(
    ("start", "action"),
    [
        ("요청", "visit"),
        ("요청", "no_show"),
        ("확정", "confirm"),
        ("취소", "confirm"),
        ("방문완료", "cancel"),
        ("노쇼", "change"),
    ],
)
def test_denied_transitions(start, action):
    with pytest.raises(InvalidTransitionError):
        getattr(state_of(start), action)()


def test_terminal_states_have_no_actions():
    for status in ("방문완료", "취소", "노쇼"):
        assert state_of(status).allowed_actions() == []


def test_allowed_actions_for_buttons():
    assert state_of("요청").allowed_actions() == ["confirm", "cancel", "change"]


def test_unknown_status():
    with pytest.raises(ValueError):
        state_of("보류")
