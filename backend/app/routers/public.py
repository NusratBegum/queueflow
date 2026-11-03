from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import queue_ops
from app.db import get_db
from app.models import Queue, Ticket, TicketStatus
from app.schemas import JoinIn, JoinOut, PublicQueueOut, PublicTicketOut

router = APIRouter(prefix="/public", tags=["customers"])


def no_store(response: Response) -> None:
    # Customers poll these endpoints; never serve a stale position from a cache.
    response.headers["Cache-Control"] = "no-store"


def queue_by_slug(slug: str, db: Session = Depends(get_db)) -> Queue:
    queue = db.scalar(select(Queue).where(Queue.slug == slug))
    if queue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Queue not found")
    return queue


def ticket_by_token(token: str, db: Session = Depends(get_db)) -> Ticket:
    ticket = db.scalar(select(Ticket).where(Ticket.token == token))
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket


@router.get("/queues/{slug}", response_model=PublicQueueOut, dependencies=[Depends(no_store)])
def queue_info(queue: Queue = Depends(queue_by_slug), db: Session = Depends(get_db)) -> PublicQueueOut:
    serving = db.scalars(
        select(Ticket)
        .where(Ticket.queue_id == queue.id, Ticket.status == TicketStatus.called.value)
        .order_by(Ticket.called_at.desc())
    )
    waiting = queue_ops.waiting_count(db, queue.id)
    return PublicQueueOut(
        name=queue.name,
        slug=queue.slug,
        is_open=queue.is_open,
        waiting=waiting,
        now_serving=[{"number": t.number, "counter": t.counter} for t in serving],
        estimated_wait_minutes=queue_ops.estimate_minutes(
            waiting, queue_ops.avg_service_minutes(db, queue.id), queue_ops.active_counters(db, queue.id)
        ),
    )


@router.post("/queues/{slug}/tickets", response_model=JoinOut, status_code=status.HTTP_201_CREATED)
def join(body: JoinIn, queue: Queue = Depends(queue_by_slug), db: Session = Depends(get_db)) -> JoinOut:
    if not queue.is_open:
        raise HTTPException(status.HTTP_409_CONFLICT, "This queue is closed right now")
    ticket = queue_ops.join_queue(db, queue, body.name)
    return JoinOut(number=ticket.number, token=ticket.token)


@router.get("/tickets/{token}", response_model=PublicTicketOut, dependencies=[Depends(no_store)])
def ticket_status(ticket: Ticket = Depends(ticket_by_token), db: Session = Depends(get_db)) -> PublicTicketOut:
    ahead = queue_ops.people_ahead(db, ticket)
    return PublicTicketOut(
        queue_name=ticket.queue.name,
        queue_slug=ticket.queue.slug,
        number=ticket.number,
        name=ticket.name,
        status=ticket.status,
        counter=ticket.counter,
        people_ahead=ahead,
        estimated_wait_minutes=queue_ops.estimate_minutes(
            ahead, queue_ops.avg_service_minutes(db, ticket.queue_id), queue_ops.active_counters(db, ticket.queue_id)
        ),
    )


@router.post("/tickets/{token}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def leave(ticket: Ticket = Depends(ticket_by_token), db: Session = Depends(get_db)) -> None:
    locked = db.scalar(select(Ticket).where(Ticket.id == ticket.id).with_for_update())
    if locked.status != TicketStatus.waiting.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a waiting ticket can be cancelled")
    locked.status = TicketStatus.cancelled.value
    locked.finished_at = datetime.now(timezone.utc)
    db.commit()
