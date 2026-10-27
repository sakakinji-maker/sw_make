"""홍보 문구 생성. (F-04)"""

from dataclasses import dataclass

from app.adapters.ai import AIClient, AIClientError
from app.services.marketing.strategies import get_strategy


@dataclass
class ContentResult:
    text: str | None
    violations: list[str]
    error: str | None = None


class MarketingService:
    def __init__(self, ai_client: AIClient) -> None:
        self.ai = ai_client

    def generate(self, channel: str, target: str, keywords: list[str]) -> ContentResult:
        strategy = get_strategy(channel)
        try:
            text = self.ai.generate(strategy.build_prompt(target, keywords))
        except AIClientError as e:
            return ContentResult(text=None, violations=[], error=f"문구 생성 실패: {e}")
        return ContentResult(text=text, violations=strategy.check(text))

    # TODO(전지호): 메뉴명·가격 DB 대조(FactChecker 재사용), 저장·목록 조회 (F-04-3)
