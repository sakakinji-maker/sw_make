"""설정(AI_PROVIDER)에 따라 사용할 AI 클라이언트를 고른다."""

from app.adapters.ai.base import AIClient
from app.adapters.ai.external_adapter import ExternalAIClient
from app.adapters.ai.mock_adapter import MockAIClient
from app.config import AI_API_KEY, AI_PROVIDER


def get_ai_client() -> AIClient:
    if AI_PROVIDER == "external":
        return ExternalAIClient(api_key=AI_API_KEY)
    return MockAIClient()
