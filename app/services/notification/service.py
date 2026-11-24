# AI-assisted (Claude)
"""예약·문의 문자 알림.

| 이벤트             | 받는 사람    |
|--------------------|-------------|
| 예약 신청          | 점주 + 고객  |
| 예약 변경(고객이)  | 점주 + 고객  |
| 예약 확정          | 고객         |
| 예약 취소(점주가)  | 고객         |
| 예약 취소(고객이)  | 고객 + 점주  |
| 문의 접수          | 점주         |
| 답변 완료          | 고객         |

모든 문자는 단문(90바이트) 안에 들어가게 짧게 쓴다. (장문은 요금이 더 비싸다)
문자 발송이 실패해도 예약·문의 처리는 그대로 성공해야 한다. 그래서 여기서 모든 SmsError를
잡아 로그만 남기고, 호출한 쪽(예약·문의 서비스)으로 예외를 올리지 않는다.
"""

import logging
from datetime import datetime

from app.adapters.sms import SmsError, SmsSender
from app.models.models import Inquiry, Reservation

logger = logging.getLogger(__name__)

WEEKDAYS = "월화수목금토일"
PREVIEW_LENGTH = 20  # 문자를 단문(90바이트)에 맞추려고 짧게 자른다.


def _at(at: datetime) -> str:
    """'11/20(목) 14:00'"""
    return f"{at:%m/%d}({WEEKDAYS[at.weekday()]}) {at:%H:%M}"


def _when(r: Reservation) -> str:
    return _at(r.reserved_at)


class Notifier:
    def __init__(self, sender: SmsSender, owner_phone: str = "") -> None:
        self.sender = sender
        self.owner_phone = owner_phone  # 비어 있으면 점주 알림은 건너뛴다.

    # ----- 발송 (실패해도 예외를 올리지 않는다) -----
    def _send(self, to: str, text: str) -> bool:
        if not to:
            print(f"[SMS 건너뜀] 받는 번호가 없습니다: {text}", flush=True)
            return False
        try:
            self.sender.send(to, text)
            return True
        except SmsError as e:
            logger.warning("문자 발송 실패: %s", e)
            return False

    def _to_owner(self, store_name: str, text: str) -> bool:
        return self._send(self.owner_phone, f"[{store_name}] {text}")

    def _to_customer(self, phone: str, store_name: str, text: str) -> bool:
        return self._send(phone, f"[{store_name}] {text}")

    # ----- 예약 (F-02) -----
    def reservation_requested(self, r: Reservation) -> None:
        self._to_owner(r.store.name, f"새 예약 요청: {r.customer.name} {_when(r)} {r.party_size}명")
        self._to_customer(
            r.customer.phone,
            r.store.name,
            f"{_when(r)} {r.party_size}명 예약 신청 접수. 확정되면 다시 알려 드립니다.",
        )

    def reservation_changed(self, r: Reservation, old_at: datetime, old_party: int) -> None:
        """고객이 날짜·시간·인원을 바꿨다. 상태가 다시 '요청'이 되므로 점주가 재확정해야 한다."""
        self._to_owner(
            r.store.name,
            f"예약 변경 요청: {r.customer.name} {_at(old_at)} {old_party}명 → "
            f"{_when(r)} {r.party_size}명",
        )
        self._to_customer(
            r.customer.phone,
            r.store.name,
            f"{_when(r)} {r.party_size}명으로 변경 접수. 확정되면 다시 알려 드립니다.",
        )

    def reservation_confirmed(self, r: Reservation) -> None:
        self._to_customer(
            r.customer.phone, r.store.name, f"{_when(r)} {r.party_size}명 예약이 확정되었습니다."
        )

    def reservation_cancelled_by_owner(self, r: Reservation) -> None:
        self._to_customer(
            r.customer.phone,
            r.store.name,
            f"{_when(r)} 예약이 매장 사정으로 취소되었습니다. 문의: {r.store.phone}",
        )

    def reservation_cancelled_by_customer(self, r: Reservation) -> None:
        self._to_customer(r.customer.phone, r.store.name, f"{_when(r)} 예약 취소가 완료되었습니다.")
        self._to_owner(r.store.name, f"예약 취소: {r.customer.name} {_when(r)} {r.party_size}명")

    # ----- 문의 (F-03) -----
    def inquiry_received(self, i: Inquiry) -> None:
        preview = i.content.strip().replace("\n", " ")
        if len(preview) > PREVIEW_LENGTH:
            preview = preview[:PREVIEW_LENGTH] + "…"
        self._to_owner(i.store.name, f"새 문의({i.customer.name}): {preview}")

    def inquiry_answered(self, i: Inquiry) -> None:
        self._to_customer(
            i.customer.phone,
            i.store.name,
            "문의 답변이 등록되었습니다. 홈페이지 '내 문의'에서 확인해 주세요.",
        )


class NullNotifier(Notifier):
    """알림을 보내지 않는다. 서비스를 직접 만드는 테스트·스크립트의 기본값."""

    def __init__(self) -> None:
        super().__init__(sender=None, owner_phone="")  # type: ignore[arg-type]

    def _send(self, to: str, text: str) -> bool:
        return False
