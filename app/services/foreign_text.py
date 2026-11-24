# AI-assisted (Claude)
"""AI가 한국어 문장에 중국어 한자·일본어 가나를 섞는 문제 처리 (F-03 답변, F-04 홍보 문구 공통).

일부 모델(예: Qwen 계열)은 지시해도 가끔 '每次都', '因此' 같은 글자를 섞는다.
글자만 지우면 문장이 깨지므로, 섞이면 같은 요청으로 다시 생성한다.
"""

import re
from collections.abc import Callable

# 한글 문장에 섞인 일본어 가나 및 한자(CJK 통합 한자) 계열 문자
FOREIGN_CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿]")
MAX_RETRIES = 2  # 처음 1번 + 다시 2번 = 최대 3번 호출


def foreign_chars(text: str) -> str:
    """섞인 외국 문자들을 이어 붙여 돌려준다. 없으면 빈 문자열."""
    return "".join(FOREIGN_CJK.findall(text or ""))


def generate_korean(generate: Callable[[], str], retries: int = MAX_RETRIES) -> str:
    """외국 문자가 없을 때까지 최대 retries번 더 생성한다.

    다시 생성하다가 AI 오류가 나면, 이미 받은 글(외국 문자가 섞였어도)을 돌려준다.
    첫 호출의 오류는 그대로 올려 보낸다(호출한 쪽의 AI 실패 처리 F-03-5·F-04).
    """
    text = generate()
    for _ in range(retries):
        if not foreign_chars(text):
            break
        try:
            text = generate()
        except Exception:  # noqa: BLE001 - 다시 생성은 '있으면 좋은' 단계라 실패해도 첫 결과를 쓴다
            break
    return text
