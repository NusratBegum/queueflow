from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import queue_ops
from app.db import get_db
from app.models import Queue, Staff, Ticket, TicketStatus
from app.schemas import BoardOut, CallNextIn, QueueIn, QueueOut, QueueStats, QueueUpdate, TicketOut, TicketUpdate
from app.security import current_staff

router = APIRouter(prefix="/queues", tags=["staff"])

SAMPLE_NAMES = ["Somchai", "Malee", "Anan", "Kanya", "Niran", "Ploy", "Arthit", "Siri", "Lek", "Nok"]

# Which status changes staff may make by hand. Calling is done by /call-next.
ALLOWED = {
    TicketStatus.called.value: {TicketStatus.served.value, TicketStatus.no_show.value},
    TicketStatus.waiting.value: {TicketStatus.cancelled.value},
}


def owned_queue(queue_id: int, staff: Staff = Depends(current_staff), db: Session = Depends(get_db)) -> Queue:
    queue = db.get(Queue, queue_id)
    if queue is None or queue.owner_id != staff.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Queue not found")
    return queue


@router.get("", response_model=list[QueueOut])
def list_queues(staff: Staff = Depends(current_staff)) -> list[Queue]:
    return staff.queues


@router.post("", response_model=QueueOut, status_code=status.HTTP_201_CREATED)
def create_queue(body: QueueIn, staff: Staff = Depends(current_staff), db: Session = Depends(get_db)) -> Queue:
    queue = Queue(owner_id=staff.id, name=body.name.strip(), slug=queue_ops.slugify(body.name))
    db.add(queue)
    db.commit()
    return queue


@router.patch("/{queue_id}", response_model=QueueOut)
def update_queue(body: QueueUpdate, queue: Queue = Depends(owned_queue), db: Session = Depends(get_db)) -> Queue:
    queue.is_open = body.is_open
    db.commit()
    return queue


@router.get("/{queue_id}/board", response_model=BoardOut)
def board(queue: Queue = Depends(owned_queue), db: Session = Depends(get_db)) -> BoardOut:
    def tickets(*statuses: str, order, limit: int | None = None) -> list[Ticket]:
        order = order if isinstance(order, tuple) else (order,)
        q = select(Ticket).where(Ticket.queue_id == queue.id, Ticket.status.in_(statuses)).order_by(*order)
        return list(db.scalars(q.limit(limit) if limit else q))

    today = queue_ops.start_of_today()
    finished_today = select(func.count()).where(Ticket.queue_id == queue.id, Ticket.finished_at >= today)
    avg_wait = db.scalar(
        select(func.avg(func.extract("epoch", Ticket.called_at - Ticket.joined_at))).where(
            Ticket.queue_id == queue.id, Ticket.called_at >= today
        )
    )
    return BoardOut(
        queue=QueueOut.model_validate(queue),
        now_serving=tickets(TicketStatus.called.value, order=Ticket.called_at),
        waiting=tickets(TicketStatus.waiting.value, order=(Ticket.service_day, Ticket.number)),
        recent=tickets(
            TicketStatus.served.value, TicketStatus.no_show.value, TicketStatus.cancelled.value,
            order=Ticket.finished_at.desc(), limit=8,
        ),
        stats=QueueStats(
            waiting=queue_ops.waiting_count(db, queue.id),
            served_today=db.scalar(finished_today.where(Ticket.status == TicketStatus.served.value)) or 0,
            no_shows_today=db.scalar(finished_today.where(Ticket.status == TicketStatus.no_show.value)) or 0,
            avg_wait_minutes_today=round(float(avg_wait) / 60, 1) if avg_wait else None,
            avg_service_minutes=queue_ops.avg_service_minutes(db, queue.id),
        ),
    )


@router.post("/{queue_id}/call-next", response_model=TicketOut)
def call_next(body: CallNextIn, queue: Queue = Depends(owned_queue), db: Session = Depends(get_db)) -> Ticket:
    ticket = queue_ops.call_next(db, queue, body.counter)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nobody is waiting")
    return ticket


@router.patch("/{queue_id}/tickets/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int, body: TicketUpdate, queue: Queue = Depends(owned_queue), db: Session = Depends(get_db)
) -> Ticket:
    ticket = db.scalar(select(Ticket).where(Ticket.id == ticket_id, Ticket.queue_id == queue.id).with_for_update())
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if body.status not in ALLOWED.get(ticket.status, set()):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot change a {ticket.status} ticket to {body.status}")
    ticket.status = body.status
    ticket.finished_at = datetime.now(timezone.utc)
    db.commit()
    return ticket


@router.post("/{queue_id}/sample-walk-ins", response_model=list[TicketOut], status_code=status.HTTP_201_CREATED)
def sample_walk_ins(queue: Queue = Depends(owned_queue), db: Session = Depends(get_db)) -> list[Ticket]:
    """Demo helper: add five walk-in customers so the board has someone to call."""
    offset = queue_ops.waiting_count(db, queue.id)
    return [queue_ops.join_queue(db, queue, SAMPLE_NAMES[(offset + i) % len(SAMPLE_NAMES)]) for i in range(5)]
