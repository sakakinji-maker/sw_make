# AI-assisted (Claude)
"""쿨SMS(SOLAPI) 문자 발송 Adapter.

쿨SMS는 현재 SOLAPI라는 이름으로 같은 API를 제공한다. (REST API v4, HMAC-SHA256 인증)
키와 발신번호는 .env에서만 읽는다. 코드·로그에 키를 남기지 않는다.
90바이트가 넘는 문자는 SOLAPI가 자동으로 장문(LMS)으로 보낸다.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime

import httpx

from app.adapters.sms.base import SmsError, SmsSender, digits

SEND_URL = "https://api.solapi.com/messages/v4/send"


class SolapiSmsSender(SmsSender):
    def __init__(self, api_key: str, api_secret: str, sender: str, timeout: float = 10) -> None:
        if not (api_key and api_secret and sender):
            raise SmsError("SMS_API_KEY, SMS_API_SECRET, SMS_SENDER를 .env에 설정해 주세요.")
        self.api_key = api_key
        self.api_secret = api_secret
        self.sender = digits(sender)  # 쿨SMS에 등록·인증한 발신번호
        self.timeout = timeout

    def _auth_header(self) -> str:
        date = datetime.now(UTC).isoformat(timespec="seconds")
        salt = secrets.token_hex(16)
        signature = hmac.new(
            self.api_secret.encode(), (date + salt).encode(), hashlib.sha256
        ).hexdigest()
        return f"HMAC-SHA256 apiKey={self.api_key}, date={date}, salt={salt}, signature={signature}"

    def send(self, to: str, text: str) -> None:
        body = {"message": {"to": digits(to), "from": self.sender, "text": text}}
        try:
            res = httpx.post(
                SEND_URL,
                json=body,
                headers={"Authorization": self._auth_header()},
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            raise SmsError(f"문자 서버에 연결하지 못했습니다: {type(e).__name__}") from e
        if res.status_code >= 400:
            # 응답 본문에는 키가 없지만, 혹시 몰라 오류 코드만 남긴다.
            try:
                code = res.json().get("errorCode", "")
            except ValueError:
                code = ""
            raise SmsError(f"문자 발송 실패 (HTTP {res.status_code} {code})".strip())
