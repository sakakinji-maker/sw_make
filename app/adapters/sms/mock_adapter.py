# AI-assisted (Claude)
"""개발·테스트용 문자 발송기. 실제로 보내지 않고 로그와 목록에만 남긴다."""

from app.adapters.sms.base import SmsError, SmsSender, digits


class MockSmsSender(SmsSender):
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail  # 발송 실패 상황을 테스트할 때 True
        self.sent: list[tuple[str, str]] = []

    def send(self, to: str, text: str) -> None:
        if self.fail:
            raise SmsError("모의 발송 실패")
        self.sent.append((digits(to), text))
        # uvicorn은 앱의 INFO 로그를 보여 주지 않으므로 터미널에 바로 찍는다.
        print(f"[SMS mock] to={digits(to)} text={text}", flush=True)
