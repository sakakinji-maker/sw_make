# AI-assisted (Claude)
"""문자 발송 공통 인터페이스 (Adapter 패턴의 Target).

알림 서비스는 이 인터페이스에만 의존한다. 문자 업체가 바뀌어도 Adapter 하나만 새로 만든다.
AI 어댑터(app/adapters/ai)와 같은 구조다.
"""

from abc import ABC, abstractmethod


class SmsError(Exception):
    """문자 발송 실패. 알림 서비스는 이 예외만 처리하면 된다."""


class SmsSender(ABC):
    @abstractmethod
    def send(self, to: str, text: str) -> None:
        """to 번호로 문자를 보낸다. 번호는 하이픈이 있어도 된다.

        Raises:
            SmsError: 설정 누락, 네트워크 오류, 업체 응답 오류 등
        """


def digits(phone: str) -> str:
    """'010-1234-5678' → '01012345678'. 문자 업체 API는 숫자만 받는다."""
    return "".join(ch for ch in phone if ch.isdigit())
