import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.adapters.ai import AIClient, AIClientError
from app.models.models import MarketingContent, MenuItem, Store
from app.repositories.marketing_repository import (
    delete_marketing_content,
    list_marketing_contents,
    save_marketing_content,
)
from app.services.foreign_text import foreign_chars, generate_korean
from app.services.inquiry.fact_checker import FactChecker
from app.services.marketing.strategies import get_strategy


@dataclass
class ContentResult:
    text: str | None
    violations: list[str]
    error: str | None = None


MENU_PRICE_PATTERN = re.compile(
    r"([가-힣A-Za-z0-9][가-힣A-Za-z0-9\s·()_-]{0,30}?)"
    r"(?:은|는|이|가)\s*(?:가격은\s*)?[\d,]+\s*원"
)
# 메뉴 이름 자리에 오지만 메뉴가 아닌 말 (D-29: "가격은 4,500원", "이 음료는 5,500원")
GENERIC_MENU_WORDS = {"가격", "음료", "메뉴", "디저트", "케이크", "주인공", "제품", "상품", "커피"}
# 한글 문장에 섞인 일본어 가나 및 한자 계열 문자를 탐지한다.
NON_KOREAN_CJK_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")


def store_info(store: Store | None, menus: list[MenuItem] | None) -> str:
    """AI에게 줄 매장 사실 정보. 이 안의 내용만 문구에 쓰게 한다."""
    lines = []
    if store is not None:
        lines.append(f"- 매장 이름: {store.name}")
        if store.address:
            lines.append(f"- 위치: {store.address}")
        if store.open_time and store.close_time:
            hours = f"{store.open_time:%H:%M}~{store.close_time:%H:%M}"
            lines.append(f"- 영업시간: {hours}")
        if store.closed_days:
            lines.append(f"- 정기휴무: {store.closed_days.replace(',', '·')}요일")
    on_sale = [m for m in menus or [] if m.on_sale]
    if on_sale:
        lines.append("- 판매 메뉴: " + ", ".join(f"{m.name} {m.price:,}원" for m in on_sale))
    return "\n".join(lines)


FIX_PROMPT = (
    "아래 글에 한국어가 아닌 글자({chars})가 섞여 있습니다.\n"
    "그 글자들을 같은 뜻의 자연스러운 한국어로 바꾸고, 나머지 내용과 줄바꿈은 그대로 두어\n"
    "글 전체를 다시 출력하세요. 설명 없이 고친 글만 출력하세요.\n\n{text}"
)


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
        extra_note: str = "",
    ) -> ContentResult:
        strategy = get_strategy(channel)

        prompt = strategy.build_prompt(target, keywords, extra_note, store_info(store, menus))
        try:
            # 중국어·일본어 문자가 섞이면 자동으로 다시 생성한다 (최대 2번 더)
            text = generate_korean(lambda: self.ai.generate(prompt))
        except AIClientError as e:
            return ContentResult(
                text=None,
                violations=[],
                error=f"문구 생성 실패: {e}",
            )
        text = self._fix_foreign(text)

        violations = strategy.check(text)
        if NON_KOREAN_CJK_PATTERN.search(text):
            violations.append(
                "중국어·일본어 등 외국어 문자가 포함되어 있습니다. "
                "문구를 확인하고 다시 생성해 주세요."
            )

        # 매장 및 메뉴 정보가 전달되면 가격과 영업시간 검증
        if store is not None and menus is not None:
            menu_prices = {menu.name: menu.price for menu in menus if menu.on_sale}

            fact_checker = FactChecker(
                menu_prices=menu_prices,
                open_time=store.open_time,
                close_time=store.close_time,
            )

            mismatches = fact_checker.check(text)

            for mismatch in mismatches:
                violations.append(f"{mismatch.kind}: {mismatch.found} - {mismatch.message}")
            registered_names = {menu.name.strip() for menu in menus if menu.on_sale}

            candidates = MENU_PRICE_PATTERN.findall(text)

            for candidate in candidates:
                menu_name = candidate.strip()

                if not _is_registered_menu(menu_name, registered_names):
                    violations.append(f"Unregistered menu name: {menu_name}")

        return ContentResult(
            text=text,
            violations=violations,
        )

    def _fix_foreign(self, text: str) -> str:
        """다시 생성해도 외국어가 남으면(긴 블로그 글에 잦음) 그 글자만 고쳐 달라고 요청한다."""
        chars = foreign_chars(text)
        if not chars:
            return text
        try:
            fixed = self.ai.generate(FIX_PROMPT.format(chars=chars, text=text))
        except AIClientError:
            return text
        # 고친 글이 더 나을 때만 바꾼다 (외국 문자가 줄었고, 길이가 크게 줄지 않음)
        if len(foreign_chars(fixed)) < len(chars) and len(fixed) >= len(text) * 0.7:
            return fixed
        return text

    def save(
        self,
        session: Session,
        store_id: int,
        channel: str,
        target: str,
        keywords: list[str],
        result: ContentResult,
    ) -> MarketingContent:
        if result.text is None:
            raise ValueError("생성에 실패한 문구는 저장할 수 없습니다.")

        return save_marketing_content(
            session=session,
            store_id=store_id,
            channel=channel,
            target=target,
            keywords=keywords,
            text=result.text,
            violations=result.violations,
        )

    def list_saved(
        self,
        session: Session,
        store_id: int,
        limit: int = 20,
    ) -> list[MarketingContent]:
        return list_marketing_contents(
            session=session,
            store_id=store_id,
            limit=limit,
        )

    def delete(
        self,
        session: Session,
        content_id: int,
        store_id: int,
    ) -> bool:
        return delete_marketing_content(
            session=session,
            store_id=store_id,
            content_id=content_id,
        )


def _is_registered_menu(candidate: str, registered_names: set[str]) -> bool:
    """정규식이 잡은 말이 등록 메뉴(또는 메뉴가 아닌 일반 단어)인지 본다. (D-29)

    정규식은 "추천 메뉴는 아메리카노이며 가격은 4,500원"처럼 앞 문장까지 함께 잡으므로
    끝이 등록 메뉴 이름이면 인정하고, 마지막 낱말이 "가격", "음료" 같은 일반 단어면 넘어간다.
    """
    if any(candidate.endswith(name) for name in registered_names):
        return True
    return candidate.split()[-1] in GENERIC_MENU_WORDS
