"""AI 클라이언트 공통 인터페이스 (Adapter 패턴의 Target).

서비스 계층은 이 인터페이스에만 의존한다. 실제 AI 제공사가 바뀌어도
Adapter 클래스 하나만 새로 만들면 된다. (기획서 NF-03)
"""

from abc import ABC, abstractmethod


class AIClientError(Exception):
    """AI 호출 실패. 서비스 계층은 이 예외만 처리하면 된다."""


class AIClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str:
        """프롬프트를 보내고 생성된 텍스트를 돌려준다.

        Raises:
            AIClientError: 네트워크 오류, 인증 실패, 응답 형식 오류 등
        """
