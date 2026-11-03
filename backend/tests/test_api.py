from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from tests.conftest import signup


def join(client: TestClient, slug: str, name: str = "Malee") -> dict:
    r = client.post(f"/api/v1/public/queues/{slug}/tickets", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "database": "ok"}


def test_login_and_duplicate_signup(client, auth):
    r = client.post("/api/v1/auth/token", data={"username": "staff@example.com", "password": "correct-horse"})
    assert r.status_code == 200 and r.json()["access_token"]
    assert client.post("/api/v1/auth/token", data={"username": "staff@example.com", "password": "nope-nope"}).status_code == 401
    r = client.post("/api/v1/auth/signup", json={"email": "STAFF@example.com", "password": "another-pass"})
    assert r.status_code == 409


def test_staff_endpoints_need_a_token(client, queue):
    assert client.get(f"/api/v1/queues/{queue['id']}/board").status_code == 401


def test_join_gives_sequential_numbers_and_positions(client, queue):
    first = join(client, queue["slug"], "Anan")
    second = join(client, queue["slug"], "Kanya")
    assert (first["number"], second["number"]) == (1, 2)
    status = client.get(f"/api/v1/public/tickets/{second['token']}")
    assert status.headers["cache-control"] == "no-store"
    body = status.json()
    assert body["status"] == "waiting" and body["people_ahead"] == 1 and body["name"] == "Kanya"
    assert client.get(f"/api/v1/public/queues/{queue['slug']}").json()["waiting"] == 2


def test_parallel_joins_never_share_a_number(client, queue):
    with ThreadPoolExecutor(max_workers=16) as pool:
        tickets = list(pool.map(lambda i: join(client, queue["slug"], f"Guest {i}"), range(16)))
    assert sorted(t["number"] for t in tickets) == list(range(1, 17))


def test_call_next_serves_in_order(client, auth, queue):
    for name in ("Anan", "Kanya", "Niran"):
        join(client, queue["slug"], name)
    called = client.post(f"/api/v1/queues/{queue['id']}/call-next", json={"counter": "Counter 1"}, headers=auth).json()
    assert (called["number"], called["status"], called["counter"]) == (1, "called", "Counter 1")
    board = client.get(f"/api/v1/queues/{queue['id']}/board", headers=auth).json()
    assert [t["number"] for t in board["now_serving"]] == [1]
    assert [t["number"] for t in board["waiting"]] == [2, 3]
    assert board["stats"]["waiting"] == 2


def test_two_counters_never_call_the_same_person(client, auth, queue):
    for i in range(6):
        join(client, queue["slug"], f"Guest {i}")

    def press(i: int) -> int:
        r = client.post(f"/api/v1/queues/{queue['id']}/call-next", json={"counter": f"Counter {i % 2 + 1}"}, headers=auth)
        return r.json()["number"] if r.status_code == 200 else 0

    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = list(pool.map(press, range(8)))
    called = [n for n in numbers if n]
    assert sorted(called) == list(range(1, 7))  # each customer called exactly once
    assert numbers.count(0) == 2                 # the extra presses found nobody waiting


def test_call_next_on_empty_queue(client, auth, queue):
    r = client.post(f"/api/v1/queues/{queue['id']}/call-next", json={"counter": "Counter 1"}, headers=auth)
    assert r.status_code == 404 and r.json()["detail"] == "Nobody is waiting"


def test_ticket_lifecycle_and_stats(client, auth, queue):
    join(client, queue["slug"], "Anan")
    join(client, queue["slug"], "Kanya")
    base = f"/api/v1/queues/{queue['id']}"
    first = client.post(f"{base}/call-next", json={"counter": "Counter 1"}, headers=auth).json()
    assert client.patch(f"{base}/tickets/{first['id']}", json={"status": "served"}, headers=auth).status_code == 200
    second = client.post(f"{base}/call-next", json={"counter": "Counter 1"}, headers=auth).json()
    assert client.patch(f"{base}/tickets/{second['id']}", json={"status": "no_show"}, headers=auth).status_code == 200
    # A served ticket can't change again.
    r = client.patch(f"{base}/tickets/{first['id']}", json={"status": "no_show"}, headers=auth)
    assert r.status_code == 409
    stats = client.get(f"{base}/board", headers=auth).json()["stats"]
    assert (stats["served_today"], stats["no_shows_today"], stats["waiting"]) == (1, 1, 0)
    assert stats["avg_wait_minutes_today"] is not None


def test_customer_can_leave_only_while_waiting(client, auth, queue):
    ticket = join(client, queue["slug"])
    assert client.post(f"/api/v1/public/tickets/{ticket['token']}/cancel").status_code == 204
    assert client.get(f"/api/v1/public/tickets/{ticket['token']}").json()["status"] == "cancelled"
    assert client.post(f"/api/v1/public/tickets/{ticket['token']}/cancel").status_code == 409
    assert client.get("/api/v1/public/tickets/not-a-real-token").status_code == 404


def test_closed_queue_refuses_new_tickets(client, auth, queue):
    r = client.patch(f"/api/v1/queues/{queue['id']}", json={"is_open": False}, headers=auth)
    assert r.json()["is_open"] is False
    r = client.post(f"/api/v1/public/queues/{queue['slug']}/tickets", json={"name": "Late"})
    assert r.status_code == 409


def test_staff_cannot_touch_another_owners_queue(client, queue):
    other = signup(client, "other@example.com")
    assert client.get(f"/api/v1/queues/{queue['id']}/board", headers=other).status_code == 404
    r = client.post(f"/api/v1/queues/{queue['id']}/call-next", json={"counter": "X"}, headers=other)
    assert r.status_code == 404


def test_sample_walk_ins(client, auth, queue):
    r = client.post(f"/api/v1/queues/{queue['id']}/sample-walk-ins", headers=auth)
    assert r.status_code == 201 and [t["number"] for t in r.json()] == [1, 2, 3, 4, 5]


def test_numbers_restart_each_day(client, queue):
    from datetime import timedelta

    from sqlalchemy import update

    from app.db import SessionLocal
    from app.models import Queue, Ticket

    join(client, queue["slug"])
    leftover = join(client, queue["slug"], "Yesterday")
    with SessionLocal() as db:  # move both tickets and the counter to yesterday
        q = db.get(Queue, queue["id"])
        yesterday = q.number_day - timedelta(days=1)
        q.number_day = yesterday
        db.execute(update(Ticket).values(service_day=yesterday))
        db.commit()
    today = join(client, queue["slug"], "Today")
    assert today["number"] == 1
    # Yesterday's unserved ticket still comes first.
    assert client.get(f"/api/v1/public/tickets/{today['token']}").json()["people_ahead"] == 2
    assert client.get(f"/api/v1/public/tickets/{leftover['token']}").json()["people_ahead"] == 1
