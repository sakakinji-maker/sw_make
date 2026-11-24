# AI-assisted (Claude)
"""AI 초안의 마크다운 기호 정리. 손님 화면에서는 **굵게**, # 제목 같은 기호가 그대로 보인다."""

import re

_BOLD = re.compile(r"(\*\*|__)(.+?)\1", re.S)  # **굵게**, __굵게__
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+", re.M)  # "## 제목"
_BULLET = re.compile(r"^(\s*)[*+]\s+", re.M)  # "* 항목" → "- 항목"


def plain_text(text: str) -> str:
    """마크다운 강조·제목 기호를 지우고 글은 그대로 둔다. 목록 기호(*)는 '-'로 바꾼다."""
    text = _BOLD.sub(r"\2", text)
    text = text.replace("**", "")  # 짝이 안 맞아 남은 기호
    text = _HEADING.sub("", text)
    return _BULLET.sub(r"\1- ", text)
