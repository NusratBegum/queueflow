from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TicketStatus(str, Enum):
    waiting = "waiting"
    called = "called"
    served = "served"
    no_show = "no_show"
    cancelled = "cancelled"


class Staff(Base):
    __tablename__ = "qf_staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    queues: Mapped[list["Queue"]] = relationship(back_populates="owner", order_by="Queue.id")


class Queue(Base):
    __tablename__ = "qf_queues"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("qf_staff.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    # Ticket numbers restart at 1 each day (Bangkok time). Both columns change in
    # one UPDATE ... RETURNING, so parallel joins can't get the same number.
    next_number: Mapped[int] = mapped_column(Integer, default=1)
    number_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[Staff] = relationship(back_populates="queues")


class Ticket(Base):
    __tablename__ = "qf_tickets"
    __table_args__ = (
        UniqueConstraint("queue_id", "service_day", "number", name="uq_qf_ticket_day_number"),
        CheckConstraint(
            "status IN ('waiting', 'called', 'served', 'no_show', 'cancelled')", name="ck_qf_ticket_status"
        ),
        Index("ix_qf_tickets_queue_status_order", "queue_id", "status", "service_day", "number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    queue_id: Mapped[int] = mapped_column(ForeignKey("qf_queues.id", ondelete="CASCADE"))
    service_day: Mapped[date] = mapped_column(Date)
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(80))
    # Secret handed only to the customer; lets them follow or leave their own ticket.
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default=TicketStatus.waiting.value)
    counter: Mapped[str | None] = mapped_column(String(40), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    queue: Mapped[Queue] = relationship()
