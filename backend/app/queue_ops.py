"""Queue logic shared by the staff and public routers."""

import re
import secrets
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from app.models import Queue, Ticket, TicketStatus

BANGKOK = ZoneInfo("Asia/Bangkok")
DEFAULT_SERVICE_MINUTES = 4.0


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "queue"
    return f"{base}-{secrets.token_hex(2)}"


def today() -> date:
    return datetime.now(BANGKOK).date()


def start_of_today() -> datetime:
    return datetime.combine(today(), time.min, tzinfo=BANGKOK).astimezone(timezone.utc)


def join_queue(db: Session, queue: Queue, name: str) -> Ticket:
    # One atomic UPDATE ... RETURNING: Postgres row-locks the queue for the rest
    # of the transaction, so parallel joins get distinct, gap-free numbers.
    # On the first join of a new day the count restarts at 1.
    day = today()
    number = db.execute(
        update(Queue)
        .where(Queue.id == queue.id)
        .values(
            next_number=case((Queue.number_day == day, Queue.next_number + 1), else_=2),
            number_day=day,
        )
        .returning(Queue.next_number - 1)
    ).scalar_one()
    ticket = Ticket(
        queue_id=queue.id, service_day=day, number=number, name=name.strip(), token=secrets.token_urlsafe(24)
    )
    db.add(ticket)
    db.commit()
    return ticket


def call_next(db: Session, queue: Queue, counter: str) -> Ticket | None:
    # SKIP LOCKED: two counters pressing "Call next" at once each get a
    # different customer instead of both calling the same one.
    ticket = db.scalars(
        select(Ticket)
        .where(Ticket.queue_id == queue.id, Ticket.status == TicketStatus.waiting.value)
        .order_by(Ticket.service_day, Ticket.number)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if ticket is None:
        db.rollback()
        return None
    ticket.status = TicketStatus.called.value
    ticket.counter = counter.strip()
    ticket.called_at = datetime.now(timezone.utc)
    db.commit()
    return ticket


def avg_service_minutes(db: Session, queue_id: int) -> float:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    seconds = db.scalar(
        select(func.avg(func.extract("epoch", Ticket.finished_at - Ticket.called_at))).where(
            Ticket.queue_id == queue_id,
            Ticket.status == TicketStatus.served.value,
            Ticket.finished_at >= since,
        )
    )
    return round(float(seconds) / 60, 1) if seconds else DEFAULT_SERVICE_MINUTES


def active_counters(db: Session, queue_id: int) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    n = db.scalar(
        select(func.count(func.distinct(Ticket.counter))).where(
            Ticket.queue_id == queue_id, Ticket.called_at >= since, Ticket.counter.is_not(None)
        )
    )
    return max(1, n or 0)


def estimate_minutes(people_ahead: int, service_minutes: float, counters: int) -> int:
    return round(people_ahead * service_minutes / counters)


def waiting_count(db: Session, queue_id: int) -> int:
    return db.scalar(
        select(func.count()).where(Ticket.queue_id == queue_id, Ticket.status == TicketStatus.waiting.value)
    ) or 0


def people_ahead(db: Session, ticket: Ticket) -> int:
    if ticket.status != TicketStatus.waiting.value:
        return 0
    return db.scalar(
        select(func.count()).where(
            Ticket.queue_id == ticket.queue_id,
            Ticket.status == TicketStatus.waiting.value,
            (Ticket.service_day < ticket.service_day)
            | ((Ticket.service_day == ticket.service_day) & (Ticket.number < ticket.number)),
        )
    ) or 0
