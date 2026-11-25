# AI-assisted (Claude) — 정회성 검토 완료
"""예약 데이터 조회·저장 (데이터 계층, F-02). 서비스는 SQL을 직접 쓰지 않고 이 클래스를 쓴다."""

from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.models import Customer, Reservation, ReservationHistory, Store
from app.services.phone import phone_digits

# 정원 계산에 포함하는 상태. 취소·노쇼·방문완료는 자리를 차지하지 않는다.
ACTIVE_STATUSES = ("요청", "확정")


class ReservationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_stores(self) -> list[Store]:
        return list(self.session.scalars(select(Store).order_by(Store.id)))

    def get_store(self, store_id: int) -> Store | None:
        return self.session.get(Store, store_id)

    def find_customer(self, phone: str) -> Customer | None:
        return self.session.scalar(select(Customer).where(_same_phone(phone)))

    def find_or_create_customer(self, name: str, phone: str) -> Customer:
        """연락처가 같으면 같은 고객으로 본다. (문의 등록과 같은 기준)"""
        customer = self.find_customer(phone)
        if customer is None:
            customer = Customer(name=name, phone=phone)
            self.session.add(customer)
        return customer

    def get(self, reservation_id: int) -> Reservation | None:
        return self.session.get(Reservation, reservation_id)

    def add(self, reservation: Reservation, history: ReservationHistory) -> Reservation:
        self.session.add_all([reservation, history])
        self.session.commit()
        return reservation

    def booked_party_size(
        self, store_id: int, start: datetime, end: datetime, exclude_id: int | None = None
    ) -> int:
        """[start, end) 시간대에 이미 잡힌 인원 합계. 변경할 때는 자기 자신을 뺀다."""
        stmt = select(func.coalesce(func.sum(Reservation.party_size), 0)).where(
            Reservation.store_id == store_id,
            Reservation.status.in_(ACTIVE_STATUSES),
            Reservation.reserved_at >= start,
            Reservation.reserved_at < end,
        )
        if exclude_id is not None:
            stmt = stmt.where(Reservation.id != exclude_id)
        return int(self.session.scalar(stmt))

    def list_by_phone(self, phone: str) -> list[Reservation]:
        """고객 본인 예약 조회 (F-02-3). 최근 일정부터."""
        stmt = (
            select(Reservation)
            .join(Reservation.customer)
            .where(_same_phone(phone))
            .order_by(Reservation.reserved_at.desc())
        )
        return list(self.session.scalars(stmt))

    def list_by_store(self, store_id: int, status: str | None = None) -> list[Reservation]:
        stmt = select(Reservation).where(Reservation.store_id == store_id)
        if status:
            stmt = stmt.where(Reservation.status == status)
        return list(self.session.scalars(stmt.order_by(Reservation.reserved_at)))

    def recent_customers(self, store_id: int, limit: int = 100, query: str = "") -> list:
        """예약 많은 고객부터 (고객, 최근 예약, 예약 수, 방문 수, 노쇼 수). 고객 이력 첫 화면용.

        단골(방문 많음)과 노쇼 손님이 위에 보이도록 예약 수 → 방문 수 → 최근 예약 순으로 정렬한다.
        query를 주면 이름 또는 번호로 거른다 (점주 고객 검색).
        """
        last = func.max(Reservation.reserved_at)
        total = func.count(Reservation.id)
        visits = func.sum(case((Reservation.status == "방문완료", 1), else_=0))
        no_shows = func.sum(case((Reservation.status == "노쇼", 1), else_=0))
        stmt = (
            select(Customer, last, total, visits, no_shows)
            .join(Reservation, Reservation.customer_id == Customer.id)
            .where(Reservation.store_id == store_id, *_customer_filter(query))
            .group_by(Customer.id)
            .order_by(total.desc(), visits.desc(), last.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).all())

    def save(self) -> None:
        self.session.commit()


def _customer_filter(query: str) -> list:
    """점주 고객 검색 조건. 숫자만 있으면 번호(뒤 4자리면 끝자리 일치), 아니면 이름 일부.

    이름은 띄어쓰기를 무시한다 ('김 서연' → '김서연').
    """
    query = query.strip()
    if not query:
        return []
    digits = phone_digits(query)
    phone = func.replace(Customer.phone, "-", "")
    if digits and digits == query.replace("-", "").replace(" ", ""):
        return [phone.endswith(digits) if len(digits) == 4 else phone.contains(digits)]
    return [func.replace(Customer.name, " ", "").contains(query.replace(" ", ""))]


def _same_phone(phone: str):
    """하이픈 유무와 상관없이 같은 번호인지 비교하는 조건."""
    return func.replace(Customer.phone, "-", "") == phone_digits(phone)
