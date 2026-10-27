"""AI가 만든 문장 속 가격·시각을 DB 값과 대조한다. (F-03-3, 기획서 12절 검증 장치)"""

import re
from dataclasses import dataclass
from datetime import time

PRICE_PATTERN = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)\s*원")
TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})")


@dataclass(frozen=True)
class Mismatch:
    kind: str  # "가격" 또는 "시각"
    found: str  # 문장에서 찾은 값
    message: str


class FactChecker:
    def __init__(self, menu_prices: dict[str, int], open_time: time, close_time: time) -> None:
        self.menu_prices = menu_prices
        self.valid_prices = set(menu_prices.values())
        self.valid_times = {open_time.strftime("%H:%M"), close_time.strftime("%H:%M")}

    def check(self, text: str) -> list[Mismatch]:
        """불일치 목록을 돌려준다. 빈 리스트면 통과."""
        mismatches: list[Mismatch] = []

        for raw in PRICE_PATTERN.findall(text):
            price = int(raw.replace(",", ""))
            if price not in self.valid_prices:
                mismatches.append(
                    Mismatch("가격", f"{raw}원", "메뉴에 등록된 가격과 일치하지 않습니다")
                )

        for hour, minute in TIME_PATTERN.findall(text):
            found = f"{int(hour):02d}:{minute}"
            if found not in self.valid_times:
                mismatches.append(Mismatch("시각", found, "등록된 영업 시작·종료 시각과 다릅니다"))

        return mismatches
