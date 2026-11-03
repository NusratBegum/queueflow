import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import CORS_ORIGINS
from app.db import engine
from app.routers import auth, public, queues


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The hosted demo creates its tables and demo queue on first start.
    if os.getenv("SEED_DEMO") == "1":
        from app.seed import seed

        try:
            seed()
        except Exception:
            # A failed seed must not take the API down; the next cold start retries.
            logging.getLogger("queueflow").exception("Demo seed failed")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="QueueFlow API",
    version="1.0.0",
    description="Walk-in queue management: customers join from their phone, staff call the next person.",
)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

for router in (auth.router, queues.router, public.router):
    app.include_router(router, prefix="/api/v1")


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
