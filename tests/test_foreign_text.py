# AI-assisted (Claude)
"""AI가 한자·가나를 섞으면 자동으로 다시 생성하는지 (F-03 답변 초안, F-04 홍보 문구)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.ai import AIClient, AIClientError
from app.db.database import Base
from app.db.seed import load_all
from app.models.models import Inquiry
from app.repositories.inquiry_repository import InquiryRepository
from app.services.foreign_text import foreign_chars, generate_korean
from app.services.inquiry.service import InquiryService
from app.services.marketing.service import MarketingService


class ScriptedAI(AIClient):
    """정해 둔 답을 차례로 돌려주는 가짜 AI. 문자열 대신 예외를 넣으면 그 차례에 실패한다."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    def generate(self, prompt: str, system: str | None = None) -> str:
        answer = self.answers[min(self.calls, len(self.answers) - 1)]
        self.calls += 1
        if isinstance(answer, Exception):
            raise answer
        return answer


CHINESE = "반가운 계절이 올每次都 딱 한 번만 #시즌메뉴"
CLEAN = "반가운 계절이 올해도 딱 한 번만 #시즌메뉴"


def test_foreign_chars():
    assert foreign_chars(CHINESE) == "每次都" and foreign_chars(CLEAN) == ""
    assert foreign_chars("こんにちは 안녕") == "こんにちは"


def test_retry_until_korean():
    ai = ScriptedAI(CHINESE, CHINESE, CLEAN)
    assert generate_korean(lambda: ai.generate("p")) == CLEAN and ai.calls == 3


def test_gives_up_after_two_retries_and_keeps_last():
    ai = ScriptedAI(CHINESE)
    assert generate_korean(lambda: ai.generate("p")) == CHINESE and ai.calls == 3


def test_retry_error_keeps_first_text():
    ai = ScriptedAI(CHINESE, AIClientError("429"))
    assert generate_korean(lambda: ai.generate("p")) == CHINESE


def test_marketing_regenerates_and_passes():
    ai = ScriptedAI(CHINESE, CLEAN)
    result = MarketingService(ai).generate("instagram", "20대 직장인", ["계절 한정 메뉴"])
    assert result.text == CLEAN and ai.calls == 2
    assert not any("외국어" in v for v in result.violations)


def test_inquiry_draft_regenerates_or_warns():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    load_all(session)
    session.commit()
    inquiry = session.get(Inquiry, 1)
    ok = InquiryService(
        ScriptedAI("因此 아메리카노는 4,500원입니다.", "아메리카노는 4,500원입니다."),
        InquiryRepository(session),
    )
    assert ok.draft_answer(inquiry.store, inquiry.store.menu_items, [], inquiry).draft == (
        "아메리카노는 4,500원입니다."
    )
    stuck = InquiryService(
        ScriptedAI("因此 아메리카노는 4,500원입니다."), InquiryRepository(session)
    )
    result = stuck.draft_answer(inquiry.store, inquiry.store.menu_items, [], inquiry)
    assert any(m.kind == "외국어" and m.found == "因此" for m in result.mismatches)
