"""AI가 만든 문장 속 가격·시각·휴무일을 DB 값과 대조한다. (F-03-3, 기획서 12절 검증 장치)"""

import re
from dataclasses import dataclass
from datetime import time

PRICE_PATTERN = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)\s*원")
TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?。\n])\s*")
WEEKDAY_PATTERN = re.compile(r"([월화수목금토일])요일")
# 휴무를 말하는 문장인지, 영업을 말하는 문장인지 가르는 단서
OFF_WORDS = ("휴무", "쉽니다", "쉬는", "쉬어", "문을 닫", "영업하지 않", "영업을 하지 않")
OPEN_WORDS = ("영업", "운영", "오픈", "문을 엽", "문을 열", "이용 가능", "방문 가능")
NO_HOLIDAY_WORDS = (
    "연중무휴",
    "휴무일 없",
    "휴무일이 없",
    "매일 영업",
    "쉬는 날 없",
    "쉬는 날이 없",
)


@dataclass(frozen=True)
class Mismatch:
    kind: str  # "가격", "시각", "휴무일"
    found: str  # 문장에서 찾은 값
    message: str


class FactChecker:
    def __init__(
        self,
        menu_prices: dict[str, int],
        open_time: time,
        close_time: time,
        closed_days: str | None = None,
    ) -> None:
        self.menu_prices = menu_prices
        self.valid_prices = set(menu_prices.values())
        self.valid_times = {open_time.strftime("%H:%M"), close_time.strftime("%H:%M")}
        # "월,화" → {"월", "화"}. None이면 휴무일 대조를 하지 않는다.
        # (마케팅 등 휴무일을 넘기지 않는 기존 호출부의 동작을 바꾸지 않기 위해)
        self.check_days = closed_days is not None
        self.closed_days = {d.strip() for d in (closed_days or "").split(",") if d.strip()}

    def check(self, text: str) -> list[Mismatch]:
        """불일치 목록을 돌려준다. 빈 리스트면 통과."""
        return self._check_prices(text) + self._check_times(text) + self._check_closed_days(text)

    def _check_prices(self, text: str) -> list[Mismatch]:
        mismatches = []
        for raw in PRICE_PATTERN.findall(text):
            if int(raw.replace(",", "")) not in self.valid_prices:
                mismatches.append(
                    Mismatch("가격", f"{raw}원", "메뉴에 등록된 가격과 일치하지 않습니다")
                )
        return mismatches

    def _check_times(self, text: str) -> list[Mismatch]:
        mismatches = []
        for hour, minute in TIME_PATTERN.findall(text):
            found = f"{int(hour):02d}:{minute}"
            if found not in self.valid_times:
                mismatches.append(Mismatch("시각", found, "등록된 영업 시작·종료 시각과 다릅니다"))
        return mismatches

    # AI-assisted (Claude) — 정회성 검토 완료
    def _check_closed_days(self, text: str) -> list[Mismatch]:
        """문장 단위로 요일과 휴무·영업 단서를 함께 보고 판단한다. (13주차 F-03-3 보강)

        정규식 기반이라 문맥을 완벽히 이해하지는 못한다. 놓치는 사례는 검증 보고서에 기록한다.
        """
        mismatches: list[Mismatch] = []
        if not self.check_days:
            return mismatches
        for sentence in SENTENCE_SPLIT.split(text):
            mismatches += self._check_sentence_days(sentence)
        return mismatches

    def _check_sentence_days(self, sentence: str) -> list[Mismatch]:
        if self.closed_days and any(w in sentence for w in NO_HOLIDAY_WORDS):
            return [Mismatch("휴무일", "휴무 없음", self._closed_message())]
        days = WEEKDAY_PATTERN.findall(sentence)
        if any(w in sentence for w in OFF_WORDS):
            return [
                Mismatch("휴무일", f"{d}요일", f"휴무일이 아닙니다 ({self._closed_message()})")
                for d in days
                if d not in self.closed_days
            ]
        if any(w in sentence for w in OPEN_WORDS):
            return [
                Mismatch("휴무일", f"{d}요일", f"이날은 휴무일입니다 ({self._closed_message()})")
                for d in days
                if d in self.closed_days
            ]
        return []

    def _closed_message(self) -> str:
        if not self.closed_days:
            return "등록된 휴무일 없음"
        return "등록된 휴무일: " + ",".join(sorted(self.closed_days, key="월화수목금토일".index))
