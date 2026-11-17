"""채널별 홍보 문구 생성 규칙 (Strategy 패턴).

새 채널 추가 = 이 파일에 클래스 하나 추가 + @register. 다른 코드는 수정하지 않는다. (NF-02)
"""

import re
from abc import ABC, abstractmethod

HASHTAG_PATTERN = re.compile(r"#\\S+")


class ChannelStrategy(ABC):
    name: str
    min_length: int = 0
    max_length: int
    min_hashtags: int = 0
    max_hashtags: int = 0
    tone: str

    @abstractmethod
    def guide(self) -> str:
        """채널 특성을 AI에게 설명하는 문장."""

    def build_prompt(self, target: str, keywords: list[str]) -> str:
        return (
            f"{self.guide()}\\n"
            f"- 홍보 대상: {target}\\n"
            f"- 키워드: {', '.join(keywords) if keywords else '없음'}\\n"
            f"- 길이: {self.min_length}~{self.max_length}자\\n"
            f"- 해시태그: {self.min_hashtags}~{self.max_hashtags}개\\n"
            f"- 어조: {self.tone}\\n"
            "- 반드시 자연스러운 한국어로 작성하고, 중국어·일본어 등 외국어 문자를 섞지 마세요.\\n"
            "- 고객을 존중하는 친절하고 정중한 말투를 사용하세요.\\n"
            "- 비꼬거나 무례한 표현, 고객을 불편하게 할 수 있는 농담은 사용하지 마세요.\\n"
            "- 홍보 대상과 채널에 어울리는 표현을 사용하고, 어색하거나 문맥에 맞지 않는 문장은 쓰지 마세요.\\n"
            "- 매장 정보로 제공되지 않은 할인, 시설, 서비스, 영업 정보는 사실처럼 만들어내지 마세요.\\n"
            "- 최종 결과에는 안내나 해설 없이 홍보 문구만 출력하세요."
        )

    def check(self, text: str) -> list[str]:
        """규칙 위반 목록을 돌려준다. (F-04-2) 빈 리스트면 통과."""
        violations = []
        length = len(text)
        if not self.min_length <= length <= self.max_length:
            violations.append(f"글자 수 {length}자 (허용 {self.min_length}~{self.max_length}자)")
        tags = len(HASHTAG_PATTERN.findall(text))
        if not self.min_hashtags <= tags <= self.max_hashtags:
            violations.append(f"해시태그 {tags}개 (허용 {self.min_hashtags}~{self.max_hashtags}개)")
        return violations


_REGISTRY: dict[str, type[ChannelStrategy]] = {}


def register(cls: type[ChannelStrategy]) -> type[ChannelStrategy]:
    _REGISTRY[cls.name] = cls
    return cls


def get_strategy(channel: str) -> ChannelStrategy:
    try:
        return _REGISTRY[channel]()
    except KeyError as e:
        raise ValueError(f"지원하지 않는 채널: {channel}") from e


def available_channels() -> list[str]:
    return list(_REGISTRY)


@register
class InstagramStrategy(ChannelStrategy):
    name = "instagram"
    min_length, max_length = 50, 300
    min_hashtags, max_hashtags = 3, 10
    tone = "친근하고 감각적인 말투, 이모지 1~3개"

    def guide(self) -> str:
        return "인스타그램 게시글을 작성하세요. 첫 문장에서 시선을 끌고 끝에 해시태그를 붙이세요."


@register
class BlogStrategy(ChannelStrategy):
    name = "blog"
    min_length, max_length = 300, 1500
    min_hashtags, max_hashtags = 0, 5
    tone = "정보 위주의 차분한 설명체"

    def guide(self) -> str:
        return "블로그 소개글을 작성하세요. 메뉴 특징과 방문 정보를 문단으로 나눠 설명하세요."


@register
class SmsStrategy(ChannelStrategy):
    name = "sms"
    min_length, max_length = 10, 80
    min_hashtags, max_hashtags = 0, 0
    tone = "짧고 명확한 안내체, 해시태그 없음"

    def guide(self) -> str:
        return "단골 고객에게 보낼 문자 메시지를 작성하세요. 핵심 혜택 한 가지만 담으세요."
