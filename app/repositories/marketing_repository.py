"""홍보 문구 DB 조회·저장 Repository (F-04)."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import MarketingContent


def save_marketing_content(
    session: Session,
    store_id: int,
    channel: str,
    target: str,
    keywords: list[str],
    text: str,
    check_result: list[str],
) -> MarketingContent:
    """홍보 문구와 규칙 검사 결과를 저장한다."""
    content = MarketingContent(
        store_id=store_id,
        channel=channel,
        target=target,
        keywords=", ".join(keywords),
        text=text,
        check_result=json.dumps(check_result, ensure_ascii=False),
    )
    session.add(content)
    session.commit()
    session.refresh(content)
    return content


def list_marketing_contents(
    session: Session, store_id: int, limit: int = 20
) -> list[MarketingContent]:
    """매장별 최근 홍보 문구를 최신순으로 조회한다."""
    if limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")
    statement = (
        select(MarketingContent)
        .where(MarketingContent.store_id == store_id)
        .order_by(MarketingContent.saved_at.desc(), MarketingContent.id.desc())
        .limit(limit)
    )
    return list(session.scalars(statement).all())
