# AI-assisted (Claude)
import logging

from app.adapters.sms import MockSmsSender, SmsError, get_sms_sender
from app.config import SMS_OWNER_PHONE
from app.services.notification.service import Notifier, NullNotifier

logger = logging.getLogger(__name__)


def get_notifier() -> Notifier:
    """.env 설정대로 알림기를 만든다. 설정이 잘못돼도 예약·문의는 막지 않고 mock으로 대신한다."""
    try:
        sender = get_sms_sender()
    except SmsError as e:
        logger.warning("문자 설정 오류로 mock 발송기를 씁니다: %s", e)
        sender = MockSmsSender()
    return Notifier(sender, owner_phone=SMS_OWNER_PHONE)


__all__ = ["Notifier", "NullNotifier", "get_notifier"]
