# QueueFlow

**Walk-in queues for clinics, salons and service counters.** Customers scan a link, join from their phone and watch their place in line. Staff call the next person from any counter, and a waiting-room screen shows who is being served.

[![CI](https://github.com/NusratBegum/queueflow/actions/workflows/ci.yml/badge.svg)](https://github.com/NusratBegum/queueflow/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![React 18](https://img.shields.io/badge/React_18-20232A?logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)

**[Open the live front desk](LIVE_URL)** · [Join as a customer](LIVE_URL/#/q/siam-smile-dental) · [Waiting-room screen](LIVE_URL/#/display/siam-smile-dental) · [API docs](API_URL/docs)
Demo login: `demo@queueflow.dev` / `demo-queue-2026`

![Front desk: today's stats, the call-next button for your counter, the waiting list and who is being served](docs/front-desk.png)

| Customer's phone | Waiting-room screen |
|---|---|
| <img src="docs/customer-ticket.png" alt="Customer ticket page showing number 007 and 4 people ahead" width="300"> | <img src="docs/waiting-room.png" alt="Waiting-room screen showing numbers 002 at Counter 2 and 001 at Counter 1" width="520"> |

### Try it in a minute

1. Open the [front desk](LIVE_URL) and press **Sign in** (the demo account is filled in).
2. Open the [customer page](LIVE_URL/#/q/siam-smile-dental) on your phone or in another tab and join with your name. You get a number, the people ahead of you and an expected wait.
3. Back at the desk, press **Call next**. Switch counters and press it again. Your phone page turns green and buzzes when it's your turn.
4. Mark people **Served** or **No-show** and watch today's stats update. If the queue runs empty, press **Add 5 sample walk-ins**.

## What it does

- **Fair numbering under load.** Joining runs one `UPDATE ... RETURNING` on the queue row, so 16 people joining at the same moment get 16 distinct, gap-free numbers. Numbers restart at 001 every day (Bangkok time).
- **Two counters never call the same person.** "Call next" picks the first waiting ticket with `SELECT ... FOR UPDATE SKIP LOCKED`. A test presses it 8 times in parallel from two counters with 6 people waiting: each person is called exactly once and the 2 extra presses get "Nobody is waiting".
- **Honest wait estimates.** Expected wait = people ahead × average service time over the last 7 days ÷ counters active in the last hour.
- **Private tickets.** Each customer gets a random token in their link. It is the only way to see or cancel that ticket, and staff endpoints need a JWT.
- **Live without WebSockets.** Pages poll every 3 seconds, only while the tab is visible, and the API sends `Cache-Control: no-store`, which works on serverless hosting.
- **Clear lifecycle.** waiting → called → served or no-show; a waiting customer can leave, and staff can remove someone. Invalid changes return `409`.

## How it works

```mermaid
flowchart LR
  Phone["Customer phone<br/>#/q/:slug, #/t/:token"] -- "poll 3 s" --> API
  Desk["Front desk<br/>React + TypeScript"] -- "JWT" --> API["FastAPI<br/>(Vercel Python function)"]
  TV["Waiting-room screen<br/>#/display/:slug"] -- "poll 3 s" --> API
  API -- "SQLAlchemy 2.0<br/>UPDATE ... RETURNING<br/>FOR UPDATE SKIP LOCKED" --> DB[("PostgreSQL<br/>(Neon)")]
```

## Stack

| Layer | Tech |
|---|---|
| Front end | React 18, TypeScript, Vite, plain CSS with light and dark themes |
| API | FastAPI, Pydantic v2, SQLAlchemy 2.0, OAuth2 + JWT, bcrypt |
| Database | PostgreSQL (Neon in production) |
| Tests | 14 pytest tests against a real PostgreSQL, including the concurrency cases; GitHub Actions also builds the front end |
| Hosting | Vercel (one project for the API, one for the front end) |

## API

| Method | Path | Who | What it does |
|---|---|---|---|
| POST | `/api/v1/auth/signup`, `/api/v1/auth/token` | staff | Create an account, log in |
| GET / POST | `/api/v1/queues` | staff | List or create queues |
| PATCH | `/api/v1/queues/{id}` | staff | Open or close a queue |
| GET | `/api/v1/queues/{id}/board` | staff | Waiting list, now serving, recent tickets and today's stats |
| POST | `/api/v1/queues/{id}/call-next` | staff | Call the next customer to a counter |
| PATCH | `/api/v1/queues/{id}/tickets/{ticket_id}` | staff | Mark served or no-show, or remove a waiting customer |
| GET | `/api/v1/public/queues/{slug}` | anyone | Queue name, people waiting, now serving, expected wait |
| POST | `/api/v1/public/queues/{slug}/tickets` | anyone | Join the queue, get a number and a private token |
| GET | `/api/v1/public/tickets/{token}` | ticket holder | Status, people ahead, expected wait, counter |
| POST | `/api/v1/public/tickets/{token}/cancel` | ticket holder | Leave the queue |

## Run it locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/queueflow
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
python -m app.seed                          # tables + a demo clinic with a week of history
uvicorn app.main:app --reload --port 8001   # http://localhost:8001/docs
```

In a second terminal:

```bash
cd frontend
npm ci
VITE_API_URL=http://localhost:8001 npm run dev   # http://localhost:5173
```

Tests need an empty PostgreSQL database:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/queueflow_test JWT_SECRET=test python -m pytest
```

## Project layout

```
backend/
  app/
    queue_ops.py     numbering, call-next, wait estimates
    models.py        staff, queues, tickets and their constraints
    routers/         auth, staff queues, public customer endpoints
    seed.py          demo clinic with 7 days of history
  tests/test_api.py  14 API tests on PostgreSQL
frontend/src/
  Staff.tsx          login and front desk
  Join.tsx           customer join page
  TicketView.tsx     customer ticket with live position
  Display.tsx        waiting-room screen
  usePoll.ts         visibility-aware polling hook
docs/                screenshots
```

## Author

Built by [Nusrat Begum](https://nusratbegum.dev).
