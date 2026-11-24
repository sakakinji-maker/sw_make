# AI-assisted (Claude)
"""설정(SMS_PROVIDER)에 따라 문자 발송기를 고른다. 기본값 mock은 실제로 보내지 않는다."""

from app.adapters.sms.base import SmsError, SmsSender, digits
from app.adapters.sms.mock_adapter import MockSmsSender
from app.adapters.sms.solapi_adapter import SolapiSmsSender
from app.config import SMS_API_KEY, SMS_API_SECRET, SMS_PROVIDER, SMS_SENDER


def get_sms_sender(provider: str = SMS_PROVIDER) -> SmsSender:
    if provider == "mock":
        return MockSmsSender()
    if provider == "solapi":
        return SolapiSmsSender(SMS_API_KEY, SMS_API_SECRET, SMS_SENDER)
    raise SmsError(f"알 수 없는 SMS_PROVIDER: {provider} (가능: mock, solapi)")


__all__ = ["MockSmsSender", "SmsError", "SmsSender", "digits", "get_sms_sender"]
