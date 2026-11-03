from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class QueueIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class QueueUpdate(BaseModel):
    is_open: bool


class QueueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    is_open: bool


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: int
    name: str
    status: str
    counter: str | None
    joined_at: datetime
    called_at: datetime | None
    finished_at: datetime | None


class CallNextIn(BaseModel):
    counter: str = Field(min_length=1, max_length=40)


class TicketUpdate(BaseModel):
    status: Literal["served", "no_show", "cancelled"]


class QueueStats(BaseModel):
    waiting: int
    served_today: int
    no_shows_today: int
    avg_wait_minutes_today: float | None
    avg_service_minutes: float


class BoardOut(BaseModel):
    queue: QueueOut
    now_serving: list[TicketOut]
    waiting: list[TicketOut]
    recent: list[TicketOut]
    stats: QueueStats


class JoinIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class JoinOut(BaseModel):
    number: int
    token: str


class PublicQueueOut(BaseModel):
    name: str
    slug: str
    is_open: bool
    waiting: int
    now_serving: list[dict[str, str | int | None]]
    estimated_wait_minutes: int


class PublicTicketOut(BaseModel):
    queue_name: str
    queue_slug: str
    number: int
    name: str
    status: str
    counter: str | None
    people_ahead: int
    estimated_wait_minutes: int
