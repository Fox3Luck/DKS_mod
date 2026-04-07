"""Pydantic models for DKS_mod API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, HttpUrl


# --- API Tokens ---

class TokenCreate(BaseModel):
    customer_id: str
    server_ids: list[str]  # which servers this token can access
    description: str = ""


class TokenResponse(BaseModel):
    id: int
    customer_id: str
    token: str  # only returned on creation
    server_ids: list[str]
    description: str
    created_at: datetime


class TokenInfo(BaseModel):
    id: int
    customer_id: str
    server_ids: list[str]
    description: str
    created_at: datetime
    last_used: datetime | None = None


# --- Webhooks ---

class WebhookEventType(str, Enum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    ALL = "all"


class WebhookCreate(BaseModel):
    url: HttpUrl
    event_types: list[WebhookEventType] = [WebhookEventType.ALL]
    secret: str | None = None  # optional shared secret for HMAC verification


class WebhookResponse(BaseModel):
    id: int
    url: str
    event_types: list[str]
    created_at: datetime
    active: bool = True


class WebhookList(BaseModel):
    webhooks: list[WebhookResponse]


# --- Events ---

class PlayerEvent(BaseModel):
    event: str  # "connect" or "disconnect"
    server_id: str
    player_name: str
    player_ucid: str
    timestamp: datetime
    tacview_url: str | None = None  # only on disconnect, signed URL


# --- Tacview ---

class TacviewFile(BaseModel):
    filename: str
    size_bytes: int
    created_at: datetime
    duration_seconds: int | None = None
    download_url: str  # signed URL


class TacviewFileList(BaseModel):
    server_id: str
    files: list[TacviewFile]


class TacviewRTTStatus(BaseModel):
    server_id: str
    enabled: bool
    host: str | None = None
    port: int | None = None


class TacviewRTTToggle(BaseModel):
    enabled: bool


# --- Olympus ---

class OlympusAccess(BaseModel):
    server_id: str
    url: str
    username: str
    password: str


# --- General ---

class ErrorResponse(BaseModel):
    detail: str


class StatusResponse(BaseModel):
    status: str
    version: str = "0.1.0"
