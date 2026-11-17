# AI-assisted (Claude) — 정회성 검토 완료
"""문의 데이터 조회·저장 (데이터 계층). 서비스는 SQL을 직접 쓰지 않고 이 클래스를 쓴다."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import Customer, Inquiry, Store


class InquiryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_stores(self) -> list[Store]:
        return list(self.session.scalars(select(Store).order_by(Store.id)))

    def get_store(self, store_id: int) -> Store | None:
        return self.session.get(Store, store_id)

    def find_or_create_customer(self, name: str, phone: str) -> Customer:
        """연락처가 같으면 같은 고객으로 본다. (UC-02와 같은 기준)"""
        customer = self.session.scalar(select(Customer).where(Customer.phone == phone))
        if customer is None:
            customer = Customer(name=name, phone=phone)
            self.session.add(customer)
        return customer

    def add(self, inquiry: Inquiry) -> Inquiry:
        self.session.add(inquiry)
        self.session.commit()
        return inquiry

    def get(self, inquiry_id: int) -> Inquiry | None:
        return self.session.get(Inquiry, inquiry_id)

    def list_by_store(self, store_id: int) -> list[Inquiry]:
        """미응답을 먼저, 그 안에서는 오래된 문의부터 보여준다."""
        stmt = (
            select(Inquiry)
            .where(Inquiry.store_id == store_id)
            .order_by((Inquiry.status != "미응답"), Inquiry.received_at)
        )
        return list(self.session.scalars(stmt))

    # AI-assisted (Claude) — 정회성 검토 완료
    def list_by_phone(self, digits: str) -> list[Inquiry]:
        """연락처(숫자만)로 고객 본인의 문의를 최신순으로 찾는다. (F-03-6)

        등록 때는 '010-1234-5678'과 '01012345678'을 모두 허용하므로 하이픈을 빼고 비교한다.
        """
        stmt = (
            select(Inquiry)
            .join(Inquiry.customer)
            .where(func.replace(Customer.phone, "-", "") == digits)
            .order_by(Inquiry.received_at.desc(), Inquiry.id.desc())
        )
        return list(self.session.scalars(stmt))

    def count_unanswered_by_store(self, store_id: int) -> int:
        """대시보드에 표시할 미응답 문의 수를 조회한다 (F-05)."""
        stmt = (
            select(func.count())
            .select_from(Inquiry)
            .where(Inquiry.store_id == store_id, Inquiry.status == "미응답")
        )
        return int(self.session.scalar(stmt) or 0)

    def save(self) -> None:
        self.session.commit()
