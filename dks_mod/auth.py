"""API token authentication system."""

import hashlib
import json
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from dks_mod.database import get_db
from dks_mod.models import TokenCreate, TokenInfo, TokenResponse

router = APIRouter(prefix="/tokens", tags=["auth"])

# Stricter rate limit for auth endpoints
_limiter = Limiter(key_func=get_remote_address)

# Admin key for token management (set via env var)
ADMIN_KEY_HEADER = APIKeyHeader(name="X-Admin-Key", auto_error=False)

# API token header for regular endpoints
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def verify_admin_key(admin_key: str = Security(ADMIN_KEY_HEADER)):
    """Verify admin key for token management endpoints."""
    import os
    expected = os.environ.get("DKS_ADMIN_KEY")
    if not expected:
        raise HTTPException(500, "DKS_ADMIN_KEY not configured")
    if not admin_key or admin_key != expected:
        raise HTTPException(403, "Invalid admin key")


async def get_current_token(api_key: str = Security(API_KEY_HEADER)) -> dict:
    """Validate API token and return token info. Used as a dependency."""
    db = await get_db()
    token_hash = _hash_token(api_key)
    row = await db.execute_fetchall(
        "SELECT id, customer_id, server_ids, description, created_at, last_used "
        "FROM api_tokens WHERE token_hash = ? AND revoked = 0",
        (token_hash,)
    )
    if not row:
        raise HTTPException(401, "Invalid or revoked API token")

    token_data = dict(row[0])
    token_data["server_ids"] = json.loads(token_data["server_ids"])

    # Update last_used
    await db.execute(
        "UPDATE api_tokens SET last_used = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), token_data["id"])
    )
    await db.commit()

    return token_data


def require_server_access(server_id: str, token: dict):
    """Check that the token has access to a specific server."""
    if server_id not in token["server_ids"] and "*" not in token["server_ids"]:
        raise HTTPException(403, f"Token does not have access to server {server_id}")


# --- Admin endpoints for token management ---

@router.post("", response_model=TokenResponse)
@_limiter.limit("10/minute")
async def create_token(request: Request, body: TokenCreate, _=Depends(verify_admin_key)):
    """Create a new API token (admin only)."""
    db = await get_db()
    raw_token = f"dks_{secrets.token_urlsafe(32)}"
    token_hash = _hash_token(raw_token)
    now = datetime.utcnow().isoformat()

    cursor = await db.execute(
        "INSERT INTO api_tokens (customer_id, token_hash, server_ids, description, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (body.customer_id, token_hash, json.dumps(body.server_ids), body.description, now)
    )
    await db.commit()

    return TokenResponse(
        id=cursor.lastrowid,
        customer_id=body.customer_id,
        token=raw_token,
        server_ids=body.server_ids,
        description=body.description,
        created_at=datetime.fromisoformat(now),
    )


@router.delete("/{token_id}")
async def revoke_token(token_id: int, _=Depends(verify_admin_key)):
    """Revoke an API token (admin only)."""
    db = await get_db()
    result = await db.execute(
        "UPDATE api_tokens SET revoked = 1 WHERE id = ?", (token_id,)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(404, "Token not found")
    return {"status": "revoked", "token_id": token_id}


@router.get("", response_model=list[TokenInfo])
async def list_tokens(_=Depends(verify_admin_key)):
    """List all active API tokens (admin only)."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, customer_id, server_ids, description, created_at, last_used "
        "FROM api_tokens WHERE revoked = 0"
    )
    return [
        TokenInfo(
            id=r["id"],
            customer_id=r["customer_id"],
            server_ids=json.loads(r["server_ids"]),
            description=r["description"],
            created_at=datetime.fromisoformat(r["created_at"]),
            last_used=datetime.fromisoformat(r["last_used"]) if r["last_used"] else None,
        )
        for r in rows
    ]
