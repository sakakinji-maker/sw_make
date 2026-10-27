"""예약 비즈니스 로직. (F-02)"""

from sqlalchemy.orm import Session

from app.models.models import Reservation, ReservationHistory
from app.services.reservation.states import state_of

ACTIONS = ("confirm", "visit", "no_show", "cancel", "change")


class ReservationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def apply(self, reservation: Reservation, action: str) -> Reservation:
        """상태 전이를 적용하고 이력을 남긴다. 허용되지 않으면 InvalidTransitionError."""
        if action not in ACTIONS:
            raise ValueError(f"알 수 없는 동작: {action}")
        current = state_of(reservation.status)
        next_state = getattr(current, action)()
        self.session.add(
            ReservationHistory(
                reservation=reservation,
                from_status=current.status.value,
                to_status=next_state.status.value,
            )
        )
        reservation.status = next_state.status.value
        self.session.commit()
        return reservation

    # TODO(한재형): create(), 휴무일·영업시간·정원 검사(F-02-2), 고객 조회(F-02-3)
