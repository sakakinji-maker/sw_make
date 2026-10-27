"""실제 생성형 AI API Adapter (Adapter 패턴의 Adapter).

TODO(정회성): 팀이 사용할 AI API가 정해지면 해당 SDK 또는 HTTP 호출로 구현한다.
- API 키는 app.config.AI_API_KEY 에서 읽는다 (.env).
- 어떤 오류든 AIClientError 로 감싸서 던진다.
"""

from app.adapters.ai.base import AIClient, AIClientError


class ExternalAIClient(AIClient):
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise AIClientError("AI_API_KEY가 설정되지 않았습니다 (.env 확인)")
        self.api_key = api_key

    def generate(self, prompt: str, system: str | None = None) -> str:
        raise AIClientError("ExternalAIClient가 아직 구현되지 않았습니다")
