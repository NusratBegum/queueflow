"""Create the tables and a demo clinic queue with a week of history."""

import random
import secrets
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select, text

from app.db import Base, SessionLocal, engine
from app.models import Queue, Staff, Ticket, TicketStatus
from app.queue_ops import BANGKOK, join_queue
from app.security import hash_password

DEMO_EMAIL = "demo@queueflow.dev"
DEMO_PASSWORD = "demo-queue-2026"
DEMO_SLUG = "siam-smile-dental"
NAMES = ["Somchai", "Malee", "Anan", "Kanya", "Niran", "Ploy", "Arthit", "Siri", "Lek", "Nok", "Pim", "Ton"]


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        # Serverless cold starts can run this in parallel; one transaction-level
        # advisory lock makes the second one wait and then see the demo exists.
        db.execute(text("SELECT pg_advisory_xact_lock(20261103)"))
        if db.scalar(select(Staff).where(Staff.email == DEMO_EMAIL)):
            return
        rng = random.Random(2026)
        staff = Staff(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        queue = Queue(owner=staff, name="Siam Smile Dental · walk-ins", slug=DEMO_SLUG)
        db.add_all([staff, queue])
        db.flush()

        # Seven past days of served and no-show tickets, so wait-time stats have data.
        today = datetime.now(BANGKOK).date()
        for days_ago in range(7, 0, -1):
            day = today - timedelta(days=days_ago)
            clock = datetime.combine(day, time(9, 0), tzinfo=BANGKOK)
            for number in range(1, rng.randint(14, 22) + 1):
                joined = clock + timedelta(minutes=rng.randint(2, 15))
                called = joined + timedelta(minutes=rng.randint(3, 25))
                served = rng.random() > 0.08
                db.add(
                    Ticket(
                        queue_id=queue.id,
                        service_day=day,
                        number=number,
                        name=rng.choice(NAMES),
                        token=secrets.token_urlsafe(24),
                        status=TicketStatus.served.value if served else TicketStatus.no_show.value,
                        counter=rng.choice(["Counter 1", "Counter 2"]),
                        joined_at=joined.astimezone(timezone.utc),
                        called_at=called.astimezone(timezone.utc),
                        finished_at=(called + timedelta(minutes=rng.randint(3, 9) if served else 2)).astimezone(timezone.utc),
                    )
                )
                clock = joined
        db.commit()

        # Today: a few people waiting right now.
        for name in ["Malee", "Anan", "Kanya", "Niran", "Ploy", "Arthit"]:
            join_queue(db, queue, name)


if __name__ == "__main__":
    seed()
    print(f"Seeded. Log in as {DEMO_EMAIL} / {DEMO_PASSWORD}")
