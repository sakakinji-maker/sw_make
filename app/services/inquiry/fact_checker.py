"""AI가 만든 문장 속 가격·시각·휴무일을 DB 값과 대조한다. (F-03-3, 기획서 12절 검증 장치)"""

import re
from dataclasses import dataclass
from datetime import time
from itertools import combinations

PRICE_PATTERN = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)\s*원")
TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})")
# "오후 9시", "10시 30분", "9시 반" 같은 한글 표기. "2시간"은 시각이 아니므로 뺀다.
KOREAN_TIME_PATTERN = re.compile(
    r"(오전|오후|아침|저녁|밤)?\s*(\d{1,2})시(?!간)(?:\s*(\d{1,2})분|\s*(반))?"
)
PM_WORDS = ("오후", "저녁", "밤")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?。\n])\s*")
WEEKDAY_PATTERN = re.compile(r"([월화수목금토일])요일")
# 휴무를 말하는 문장인지, 영업을 말하는 문장인지 가르는 단서
OFF_WORDS = ("휴무", "쉽니다", "쉬는", "쉬어", "문을 닫", "영업하지 않", "영업을 하지 않")
OPEN_WORDS = ("영업", "운영", "오픈", "문을 엽", "문을 열", "이용 가능", "방문 가능")
TOTAL_WORDS = ("총", "합계", "합쳐", "모두", "함께", "같이", "더하면", "추가하면")
MAX_TOTAL_ITEMS = 4  # 합계로 인정할 메뉴 조합의 최대 개수
EXCEPT_WORDS = ("제외", "빼고", "말고")
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

    def check(self, text: str, quoted: str = "") -> list[Mismatch]:
        """불일치 목록을 돌려준다. 빈 리스트면 통과.

        quoted: 고객 문의 원문. 초안이 고객이 말한 시각("저녁 8시 반에 가도 되나요?")을
        그대로 인용한 경우는 매장 정보 주장이 아니므로 시각 대조에서 뺀다. (13주차 실험 반영)
        """
        times = [m for m in self._check_times(text) if not _quoted(m.found, quoted)]
        return self._check_prices(text) + times + self._check_closed_days(text)

    # AI-assisted (Claude) — 정회성 검토 완료
    def _check_prices(self, text: str) -> list[Mismatch]:
        """가격 앞에 메뉴 이름이 있으면 그 메뉴 가격과, 없으면 등록된 가격 전체와 비교한다.

        13주차 오류 삽입 실험에서 '밤라떼 6,500원'(치즈케이크 가격)처럼 다른 메뉴 가격을
        말하면 놓치는 문제가 나와 메뉴별 대조를 추가했다.
        """
        mismatches = []
        totals = self._possible_totals(text)
        start = 0
        for match in PRICE_PATTERN.finditer(text):
            raw, segment = match.group(1), text[start : match.start()]
            start = match.end()
            if int(raw.replace(",", "")) in totals and any(w in segment for w in TOTAL_WORDS):
                continue  # '총 8,300원'처럼 글에 나온 메뉴 가격의 합 (13주차 실험 반영)
            mismatch = self._price_mismatch(self._menus_before(segment), raw)
            if mismatch:
                mismatches.append(mismatch)
        return mismatches

    def _possible_totals(self, text: str) -> set[int]:
        """글에 나온 메뉴 2~4개를 고른 가격 합 전체."""
        prices = [price for name, price in self.menu_prices.items() if name in text]
        return {
            sum(combo)
            for size in range(2, min(len(prices), MAX_TOTAL_ITEMS) + 1)
            for combo in combinations(prices, size)
        }

    def _menus_before(self, segment: str) -> list[str]:
        """앞 가격(또는 문장 시작)부터 이 가격 사이에 나온 메뉴 이름. 가까운 순서."""
        segment = SENTENCE_SPLIT.split(segment)[-1]
        found = [(segment.rfind(name) + len(name), name) for name in self.menu_prices]
        return [name for end, name in sorted(found, reverse=True) if end >= len(name)]

    def _price_mismatch(self, menus: list[str], raw: str) -> Mismatch | None:
        """'A와 B는 각각 4,500원, 6,000원'처럼 메뉴를 나열한 경우를 위해, 구간 안의 메뉴 중
        하나와 맞으면 통과시킨다. 하나도 맞지 않으면 가장 가까운 메뉴 가격을 알려준다."""
        price = int(raw.replace(",", ""))
        if not menus:
            if price in self.valid_prices:
                return None
            return Mismatch("가격", f"{raw}원", "메뉴에 등록된 가격과 일치하지 않습니다")
        if price in {self.menu_prices[m] for m in menus}:
            return None
        menu = menus[0]
        registered = f"{self.menu_prices[menu]:,}원"
        return Mismatch("가격", f"{raw}원", f"{menu}의 등록 가격은 {registered}입니다")

    def _check_times(self, text: str) -> list[Mismatch]:
        mismatches = []
        for hour, minute in TIME_PATTERN.findall(text):
            found = f"{int(hour):02d}:{minute}"
            if found not in self.valid_times:
                mismatches.append(Mismatch("시각", found, "등록된 영업 시작·종료 시각과 다릅니다"))
        return mismatches + self._check_korean_times(text)

    def _check_korean_times(self, text: str) -> list[Mismatch]:
        """'오후 10시'처럼 쓴 시각. 오전·오후가 없으면 12시간 차이 나는 두 경우를 모두 인정한다."""
        mismatches = []
        for match in KOREAN_TIME_PATTERN.finditer(text):
            ampm, hour, minute, half = match.groups()
            hour, minute = int(hour), 30 if half else int(minute or 0)
            candidates = {hour % 12 + 12} if ampm in PM_WORDS else {hour % 24}
            if ampm is None and hour < 12:
                candidates.add(hour + 12)
            if not {f"{h:02d}:{minute:02d}" for h in candidates} & self.valid_times:
                found = match.group(0).strip()
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
        if any(w in sentence for w in EXCEPT_WORDS):
            return self._check_except_days(sentence)
        if self.closed_days and any(w in sentence for w in NO_HOLIDAY_WORDS):
            return [Mismatch("휴무일", "휴무 없음", self._closed_message())]
        mismatches = []
        for day, clause in _day_clauses(sentence):
            # 요일 뒤 구절에 단서가 없으면("월요일, 화요일은 휴무") 문장 전체를 본다.
            context = clause if _has_any(clause, OFF_WORDS + OPEN_WORDS) else sentence
            if _has_any(context, OFF_WORDS) and day not in self.closed_days:
                message = f"휴무일이 아닙니다 ({self._closed_message()})"
            elif not _has_any(context, OFF_WORDS) and _has_any(context, OPEN_WORDS):
                if day not in self.closed_days:
                    continue
                message = f"이날은 휴무일입니다 ({self._closed_message()})"
            else:
                continue
            mismatches.append(Mismatch("휴무일", f"{day}요일", message))
        return mismatches

    def _check_except_days(self, sentence: str) -> list[Mismatch]:
        """'월요일을 제외하고 매일 영업'처럼 뺀 요일 = 휴무일이라고 말하는 문장."""
        excluded = set(WEEKDAY_PATTERN.findall(sentence))
        not_closed = sorted(excluded - self.closed_days, key="월화수목금토일".index)
        said_open = sorted(self.closed_days - excluded, key="월화수목금토일".index)
        message = self._closed_message()
        return [
            Mismatch("휴무일", f"{d}요일", f"휴무일이 아닙니다 ({message})") for d in not_closed
        ] + [Mismatch("휴무일", f"{d}요일", f"이날은 휴무일입니다 ({message})") for d in said_open]

    def _closed_message(self) -> str:
        if not self.closed_days:
            return "등록된 휴무일 없음"
        return "등록된 휴무일: " + ",".join(sorted(self.closed_days, key="월화수목금토일".index))


def _quoted(found: str, quoted: str) -> bool:
    """찾은 시각 표현이 고객 문의에 그대로 있었는지 (공백 무시)."""
    return bool(quoted) and found.replace(" ", "") in quoted.replace(" ", "")


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def _day_clauses(sentence: str) -> list[tuple[str, str]]:
    """요일마다 그 요일부터 다음 요일 앞까지의 구절을 돌려준다. (D-30)

    "월요일은 휴무이며, 화요일부터 정상 영업합니다"에서 화요일을 휴무로 잡지 않도록
    한 문장 안에서도 요일별로 가까운 단서를 본다.
    """
    matches = list(WEEKDAY_PATTERN.finditer(sentence))
    ends = [m.start() for m in matches[1:]] + [len(sentence)]
    return [(m.group(1), sentence[m.start() : end]) for m, end in zip(matches, ends, strict=False)]
