"""Tacview file management, signed download URLs, and RTT control."""

import hashlib
import hmac
import logging
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from dks_mod.auth import get_current_token, require_server_access
from dks_mod.config import settings
from dks_mod.database import get_db
from dks_mod.models import TacviewFile, TacviewFileList, TacviewRTTStatus, TacviewRTTToggle

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/servers", tags=["tacview"])

# Default Tacview path on DCS VMs (relative to user profile)
DEFAULT_TACVIEW_PATH = r"Saved Games\DCS.openbeta_server\Tacview"

# Tacview RTT default port (matches DCS server default)
TACVIEW_RTT_PORT = 42674

# fox3-agent HTTP port on each DCS VM
AGENT_PORT = 2025


def _generate_signed_url(server_id: str, filename: str) -> str:
    """Generate a time-limited signed URL for Tacview file download."""
    expires = int(time.time()) + settings.tacview_url_expiry
    message = f"{server_id}:{filename}:{expires}"
    sig = hmac.new(
        settings.secret_key.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return (
        f"{settings.api_prefix}/servers/{server_id}/tacview/download"
        f"?file={filename}&expires={expires}&sig={sig}"
    )


def _verify_signed_url(server_id: str, filename: str, expires: int, sig: str) -> bool:
    """Verify a signed Tacview download URL."""
    if time.time() > expires:
        return False
    message = f"{server_id}:{filename}:{expires}"
    expected = hmac.new(
        settings.secret_key.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(sig, expected)


@router.get("/{server_id}/tacview", response_model=TacviewFileList)
async def list_tacview_files(
    server_id: str,
    token: dict = Depends(get_current_token),
):
    """List available Tacview files for a server."""
    require_server_access(server_id, token)

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT ip, tacview_path FROM servers WHERE id = ?", (server_id,)
    )
    if not rows:
        raise HTTPException(404, f"Server {server_id} not found")

    server = dict(rows[0])
    agent_url = f"http://{server['ip']}:{AGENT_PORT}/acmi"

    logger.info("Listing Tacview files for server %s via agent at %s", server_id, agent_url)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(agent_url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(504, "Agent on server did not respond in time")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"Agent returned {exc.response.status_code}")
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Agent unreachable: {exc}")

    files = []
    for f in data.get("files", []):
        files.append(TacviewFile(
            filename=f["name"],
            size_bytes=f["size"],
            created_at=datetime.fromisoformat(f["modified"].replace("Z", "+00:00")),
            duration_seconds=None,
            download_url=_generate_signed_url(server_id, f["name"]),
        ))

    return TacviewFileList(server_id=server_id, files=files)


@router.get("/{server_id}/tacview/download")
async def download_tacview_file(
    server_id: str,
    file: str = Query(...),
    expires: int = Query(...),
    sig: str = Query(...),
):
    """Download a Tacview file using a signed URL (no API key needed)."""
    if not _verify_signed_url(server_id, file, expires, sig):
        raise HTTPException(403, "Invalid or expired download link")

    if ".." in file or "/" in file or "\\" in file:
        raise HTTPException(400, "Invalid filename")

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT ip, tacview_path FROM servers WHERE id = ?", (server_id,)
    )
    if not rows:
        raise HTTPException(404, f"Server {server_id} not found")

    server = dict(rows[0])
    ip = server["ip"]

    # Stream the file from the fox3-agent files endpoint.
    # Agent files root is Missions\; Tacview recordings live in Missions\Tacview\.
    agent_url = f"http://{ip}:{AGENT_PORT}/files/download"
    agent_headers = {"X-Agent-Key": settings.agent_key}
    agent_params = {"path": f"Tacview\\{file}"}

    logger.info("Streaming Tacview file %s for server %s from agent %s", file, server_id, ip)

    async def _stream():
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "GET", agent_url, params=agent_params, headers=agent_headers
            ) as r:
                r.raise_for_status()
                async for chunk in r.aiter_bytes(65536):
                    yield chunk

    return StreamingResponse(
        _stream(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file}"'},
    )


@router.get("/{server_id}/tacview/rtt", response_model=TacviewRTTStatus)
async def get_rtt_status(
    server_id: str,
    token: dict = Depends(get_current_token),
):
    """Get Tacview Real-Time Telemetry status for a server.

    RTT is enabled by default on all Fox3 DCS servers (options.lua).
    Host is the server's public IP; port is the standard Tacview RTT port 42674.
    """
    require_server_access(server_id, token)

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT ip, public_ip FROM servers WHERE id = ?", (server_id,)
    )
    if not rows:
        raise HTTPException(404, f"Server {server_id} not found")

    server = dict(rows[0])
    # RTT clients connect via the public IP, not Tailscale
    host = server["public_ip"] or server["ip"]

    return TacviewRTTStatus(
        server_id=server_id,
        enabled=True,
        host=host,
        port=TACVIEW_RTT_PORT,
    )


@router.post("/{server_id}/tacview/rtt", response_model=TacviewRTTStatus)
async def toggle_rtt(
    server_id: str,
    body: TacviewRTTToggle,
    token: dict = Depends(get_current_token),
):
    """Enable or disable Tacview Real-Time Telemetry on a server.

    NOTE: RTT toggling via API is not yet implemented. The endpoint
    returns the requested state but does not modify the server config.
    RTT is enabled by default on all Fox3 servers.
    """
    require_server_access(server_id, token)

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT ip, public_ip FROM servers WHERE id = ?", (server_id,)
    )
    if not rows:
        raise HTTPException(404, f"Server {server_id} not found")

    server = dict(rows[0])
    host = server["public_ip"] or server["ip"]

    logger.info("RTT toggle requested for %s: enabled=%s (not yet implemented)", server_id, body.enabled)

    return TacviewRTTStatus(
        server_id=server_id,
        enabled=body.enabled,
        host=host,
        port=TACVIEW_RTT_PORT,
    )
