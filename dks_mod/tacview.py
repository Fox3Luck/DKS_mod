"""Tacview file management, signed download URLs, and RTT control."""

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from pathlib import PureWindowsPath

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from dks_mod.auth import get_current_token, require_server_access
from dks_mod.config import settings
from dks_mod.database import get_db
from dks_mod.models import TacviewFile, TacviewFileList, TacviewRTTStatus, TacviewRTTToggle

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/servers", tags=["tacview"])

# Default Tacview path on DCS VMs (relative to user profile)
DEFAULT_TACVIEW_PATH = r"Saved Games\DCS.openbeta_server\Tacview"


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
    tacview_path = server["tacview_path"] or DEFAULT_TACVIEW_PATH

    # TODO: Connect to VM via SMB/SSH and list .acmi/.zip files
    # For now, return the structure that will be populated when VM access is wired up
    #
    # Implementation pattern:
    # 1. SSH/WinRM to server IP
    # 2. List files in tacview_path
    # 3. Get file metadata (size, creation date)
    # 4. Generate signed download URLs

    logger.info("Listing Tacview files for server %s at %s", server_id, server["ip"])

    # Placeholder — will be populated by VM file listing
    return TacviewFileList(server_id=server_id, files=[])


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

    # Validate filename to prevent path traversal
    if ".." in file or "/" in file or "\\" in file:
        raise HTTPException(400, "Invalid filename")

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT ip, tacview_path FROM servers WHERE id = ?", (server_id,)
    )
    if not rows:
        raise HTTPException(404, f"Server {server_id} not found")

    server = dict(rows[0])
    tacview_path = server["tacview_path"] or DEFAULT_TACVIEW_PATH

    # TODO: Fetch file from VM via SMB/SSH and stream it back
    # Implementation pattern:
    # 1. Connect to VM SMB share or SSH
    # 2. Read file from tacview_path/file
    # 3. Stream response with appropriate content-type
    #
    # return StreamingResponse(file_stream, media_type="application/octet-stream",
    #     headers={"Content-Disposition": f"attachment; filename={file}"})

    raise HTTPException(501, "Tacview file download not yet wired to VM access")


@router.get("/{server_id}/tacview/rtt", response_model=TacviewRTTStatus)
async def get_rtt_status(
    server_id: str,
    token: dict = Depends(get_current_token),
):
    """Get Tacview Real-Time Telemetry status for a server."""
    require_server_access(server_id, token)

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT ip FROM servers WHERE id = ?", (server_id,)
    )
    if not rows:
        raise HTTPException(404, f"Server {server_id} not found")

    server = dict(rows[0])

    # TODO: SSH to VM, read TacViewOptions.lua, check RTT settings
    # Parse: tacviewRealTimeTelemetryEnabled = true/false
    # Parse: tacviewRealTimeTelemetryPort = 42674

    return TacviewRTTStatus(
        server_id=server_id,
        enabled=False,  # placeholder
        host=server["ip"],
        port=42674,  # default Tacview RTT port
    )


@router.post("/{server_id}/tacview/rtt", response_model=TacviewRTTStatus)
async def toggle_rtt(
    server_id: str,
    body: TacviewRTTToggle,
    token: dict = Depends(get_current_token),
):
    """Enable or disable Tacview Real-Time Telemetry on a server."""
    require_server_access(server_id, token)

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT ip FROM servers WHERE id = ?", (server_id,)
    )
    if not rows:
        raise HTTPException(404, f"Server {server_id} not found")

    server = dict(rows[0])

    # TODO: SSH to VM and modify TacViewOptions.lua
    # Or use file-based C2: drop a trigger file that the VM's update.bat processes
    #
    # Pattern:
    # 1. SSH to server IP
    # 2. Modify Saved Games\DCS...\Config\TacViewOptions.lua
    #    Set tacviewRealTimeTelemetryEnabled = true/false
    # 3. May require mission restart for changes to take effect
    #
    # File-based C2 alternative:
    # 1. Write .rtt-enable or .rtt-disable trigger file to ServerControl/
    # 2. Nextcloud syncs to VM
    # 3. update.bat or dedicated script processes trigger

    logger.info("RTT toggle for %s: enabled=%s", server_id, body.enabled)

    return TacviewRTTStatus(
        server_id=server_id,
        enabled=body.enabled,
        host=server["ip"],
        port=42674,
    )
