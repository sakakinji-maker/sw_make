# AI-assisted (Claude)
"""연락처 형식 통일. 입력은 하이픈 유무와 상관없이 받고, 저장은 010-1234-5678 모양으로 한다."""

import re


def phone_digits(phone: str) -> str:
    """'010-1234-5678' → '01012345678'. 비교할 때 쓴다."""
    return re.sub(r"\D", "", phone or "")


def normalize_phone(phone: str) -> str:
    """하이픈을 넣은 표준 모양으로 바꾼다. 휴대폰 번호 모양이 아니면 앞뒤 공백만 지운다."""
    d = phone_digits(phone)
    if len(d) == 11:
        return f"{d[:3]}-{d[3:7]}-{d[7:]}"
    if len(d) == 10:
        return f"{d[:3]}-{d[3:6]}-{d[6:]}"
    return (phone or "").strip()
