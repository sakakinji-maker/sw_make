"""채널별 홍보 문구 생성 규칙 (Strategy 패턴).

새 채널 추가 = 이 파일에 클래스 하나 추가 + @register. 다른 코드는 수정하지 않는다. (NF-02)
"""

import re
from abc import ABC, abstractmethod

HASHTAG_PATTERN = re.compile(r"#\S+")


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

    def build_prompt(
        self, target: str, keywords: list[str], extra_note: str = "", store_info: str = ""
    ) -> str:
        prompt = f"{self.guide()}\n"
        if store_info:
            # 매장 정보를 주지 않으면 AI가 메뉴·가격·위치를 지어낸다 (블로그에서 특히 심함)
            prompt += f"\n[매장 정보 — 사실로 쓸 수 있는 것은 이것뿐입니다]\n{store_info}\n\n"
        prompt += (
            f"- 홍보 대상: {target}\n- 키워드: {', '.join(keywords) if keywords else '없음'}\n"
        )
        if extra_note:
            prompt += f"- 사장님이 꼭 넣어 달라고 한 내용: {extra_note}\n"
        prompt += (
            f"- 길이: {self.min_length}~{self.max_length}자\n"
            f"- 해시태그: {self.min_hashtags}~{self.max_hashtags}개\n"
            f"- 어조: {self.tone}\n"
            "- 반드시 자연스러운 한국어로 작성하고, 중국어·일본어 등 외국어 문자를 섞지 마세요.\n"
            "  한자는 한 글자도 쓰지 말고 모두 한글로 쓰세요.\n"
            "- 고객을 존중하는 친절하고 정중한 말투를 사용하세요.\n"
            "- 비꼬거나 무례한 표현, 고객을 불편하게 할 수 있는 농담은 사용하지 마세요.\n"
            "- 홍보 대상과 채널에 어울리는 표현을 사용하세요.\n"
            "- 어색하거나 문맥에 맞지 않는 문장은 쓰지 마세요.\n"
            "- 매장 정보에 없는 할인, 시설, 서비스, 영업 정보를\n"
            "  사실처럼 만들어내지 마세요.\n"
            "- 최종 결과에는 안내나 해설 없이 홍보 문구만 출력하세요."
        )
        return prompt

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
    # 너무 길게 쓰게 하면 뒤로 갈수록 외국어가 섞이고 내용이 흐트러져서 500~1000자로 줄였다
    min_length, max_length = 400, 1000
    min_hashtags, max_hashtags = 0, 5
    tone = "정보 위주의 차분하고 다정한 설명체(~해요, ~입니다)"

    def guide(self) -> str:
        return (
            "카페 블로그 소개글을 작성하세요. 아래 순서를 지키세요.\n"
            "1) 첫 줄: 글 제목 한 줄\n"
            "2) 첫 문단: 인사와 이번 글에서 소개할 내용 (2~3문장)\n"
            "3) 둘째 문단: 추천 메뉴 1~2개의 맛·특징과 가격 (매장 정보의 메뉴·가격만 사용)\n"
            "4) 셋째 문단: 홍보 대상에게 이 카페가 좋은 이유 (2~3문장)\n"
            "5) 마지막 문단: 영업시간·휴무일·위치 등 방문 안내\n"
            "문단 사이는 빈 줄로 나누고, 마크다운 기호(**, #제목)는 쓰지 마세요."
        )


@register
class SmsStrategy(ChannelStrategy):
    name = "sms"
    # 단문(90바이트=한글 45자)은 너무 짧아서 장문 문자(LMS) 분량으로 늘렸다
    min_length, max_length = 80, 200
    min_hashtags, max_hashtags = 0, 0
    tone = "다정하고 명확한 안내체, 해시태그 없음, 이모지 0~2개"

    def guide(self) -> str:
        return (
            "단골 고객에게 보낼 장문 문자 메시지를 작성하세요. 3~5문장으로 아래 순서를 지키세요.\n"
            "1) 매장 이름을 넣은 짧은 인사\n"
            "2) 소개할 메뉴나 소식 (매장 정보의 메뉴·가격만 사용)\n"
            "3) 지금 방문하면 좋은 이유 한 가지\n"
            "4) 영업시간 등 방문 안내 한 줄"
        )
