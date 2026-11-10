"""홍보 문구 생성 및 저장. (F-04)"""

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.adapters.ai import AIClient, AIClientError
from app.models.models import MarketingContent, MenuItem, Store
from app.repositories.marketing_repository import (
    list_marketing_contents,
    save_marketing_content,
)
from app.services.inquiry.fact_checker import FactChecker
from app.services.marketing.strategies import get_strategy


@dataclass
class ContentResult:
    text: str | None
    violations: list[str]
    error: str | None = None


class MarketingService:
    def __init__(self, ai_client: AIClient) -> None:
        self.ai = ai_client

    def generate(
        self,
        channel: str,
        target: str,
        keywords: list[str],
        store: Store | None = None,
        menus: list[MenuItem] | None = None,
    ) -> ContentResult:
        """문구를 생성하고, 매장 정보가 전달되면 등록된 가격·영업시간을 대조한다."""
        strategy = get_strategy(channel)
        try:
            text = self.ai.generate(strategy.build_prompt(target, keywords))
        except AIClientError as e:
            return ContentResult(text=None, violations=[], error=f"문구 생성 실패: {e}")

        violations = strategy.check(text)
        if store is not None and menus is not None:
            checker = FactChecker(
                menu_prices={menu.name: menu.price for menu in menus if menu.on_sale},
                open_time=store.open_time,
                close_time=store.close_time,
            )
            violations.extend(
                f"{mismatch.kind}: {mismatch.found} - {mismatch.message}"
                for mismatch in checker.check(text)
            )
        return ContentResult(text=text, violations=violations)

    def save(
        self,
        session: Session,
        store_id: int,
        channel: str,
        target: str,
        keywords: list[str],
        result: ContentResult,
    ) -> MarketingContent:
        """생성 결과를 DB에 저장한다. AI 생성 실패 결과는 저장하지 않는다."""
        if result.text is None:
            raise ValueError("생성된 문구가 없어 저장할 수 없습니다.")
        return save_marketing_content(
            session=session,
            store_id=store_id,
            channel=channel,
            target=target,
            keywords=keywords,
            text=result.text,
            check_result=result.violations,
        )

    def list_saved(
        self, session: Session, store_id: int, limit: int = 20
    ) -> list[MarketingContent]:
        """매장의 최근 저장 문구를 조회한다."""
        return list_marketing_contents(session, store_id, limit)
