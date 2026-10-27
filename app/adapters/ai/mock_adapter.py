"""개발·테스트용 가짜 AI. 실제 API를 호출하지 않는다."""

from app.adapters.ai.base import AIClient, AIClientError


class MockAIClient(AIClient):
    def __init__(self, fixed_response: str | None = None, fail: bool = False) -> None:
        self.fixed_response = fixed_response
        self.fail = fail
        self.last_prompt: str | None = None

    def generate(self, prompt: str, system: str | None = None) -> str:
        self.last_prompt = prompt
        if self.fail:
            raise AIClientError("Mock AI 호출 실패(테스트용)")
        if self.fixed_response is not None:
            return self.fixed_response
        return "[Mock 응답] 문의 감사합니다. 영업시간은 09:00부터 21:00까지입니다."
