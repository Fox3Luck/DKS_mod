"""Webhook registration and event dispatch."""

import hashlib
import hmac
import json
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends

from dks_mod.auth import get_current_token
from dks_mod.config import settings
from dks_mod.database import get_db
from dks_mod.models import WebhookCreate, WebhookList, WebhookResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("", response_model=WebhookResponse)
async def register_webhook(body: WebhookCreate, token: dict = Depends(get_current_token)):
    """Register a webhook URL to receive events."""
    db = await get_db()
    event_types = json.dumps([e.value for e in body.event_types])
    now = datetime.utcnow().isoformat()

    cursor = await db.execute(
        "INSERT INTO webhooks (token_id, url, event_types, secret, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (token["id"], str(body.url), event_types, body.secret, now)
    )
    await db.commit()

    return WebhookResponse(
        id=cursor.lastrowid,
        url=str(body.url),
        event_types=[e.value for e in body.event_types],
        created_at=datetime.fromisoformat(now),
        active=True,
    )


@router.delete("/{webhook_id}")
async def unregister_webhook(webhook_id: int, token: dict = Depends(get_current_token)):
    """Unregister a webhook."""
    db = await get_db()
    result = await db.execute(
        "DELETE FROM webhooks WHERE id = ? AND token_id = ?",
        (webhook_id, token["id"])
    )
    await db.commit()
    if result.rowcount == 0:
        return {"status": "not_found", "webhook_id": webhook_id}
    return {"status": "deleted", "webhook_id": webhook_id}


@router.get("", response_model=WebhookList)
async def list_webhooks(token: dict = Depends(get_current_token)):
    """List all registered webhooks for this token."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, url, event_types, created_at, active FROM webhooks WHERE token_id = ?",
        (token["id"],)
    )
    return WebhookList(
        webhooks=[
            WebhookResponse(
                id=r["id"],
                url=r["url"],
                event_types=json.loads(r["event_types"]),
                created_at=datetime.fromisoformat(r["created_at"]),
                active=bool(r["active"]),
            )
            for r in rows
        ]
    )


def _sign_payload(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for a webhook payload."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def dispatch_event(event_type: str, payload: dict):
    """Dispatch an event to all matching webhooks."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT w.id, w.url, w.secret, w.event_types FROM webhooks w "
        "JOIN api_tokens t ON w.token_id = t.id "
        "WHERE w.active = 1 AND t.revoked = 0"
    )

    payload_json = json.dumps(payload, default=str)

    async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
        for row in rows:
            event_types = json.loads(row["event_types"])
            if "all" not in event_types and event_type not in event_types:
                continue

            headers = {"Content-Type": "application/json"}
            if row["secret"]:
                sig = _sign_payload(payload_json, row["secret"])
                headers["X-DKS-Signature"] = f"sha256={sig}"

            success = False
            status_code = None
            for attempt in range(1, settings.webhook_max_retries + 1):
                try:
                    resp = await client.post(
                        row["url"], content=payload_json, headers=headers
                    )
                    status_code = resp.status_code
                    if 200 <= resp.status_code < 300:
                        success = True
                        break
                    logger.warning(
                        "Webhook %s delivery attempt %d failed: HTTP %d",
                        row["id"], attempt, resp.status_code
                    )
                except httpx.RequestError as e:
                    logger.warning(
                        "Webhook %s delivery attempt %d error: %s",
                        row["id"], attempt, e
                    )

            # Record delivery attempt
            await db.execute(
                "INSERT INTO webhook_deliveries "
                "(webhook_id, event_type, payload, status_code, attempts, last_attempt, success) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["id"], event_type, payload_json, status_code,
                 settings.webhook_max_retries, datetime.utcnow().isoformat(), int(success))
            )
            await db.commit()

            if not success:
                logger.error("Webhook %s delivery failed after %d attempts", row["id"], settings.webhook_max_retries)
