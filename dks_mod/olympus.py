"""DCS Olympus credential retrieval."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from dks_mod.auth import get_current_token, require_server_access
from dks_mod.database import get_db
from dks_mod.models import OlympusAccess

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/servers", tags=["olympus"])


@router.get("/{server_id}/olympus", response_model=OlympusAccess)
async def get_olympus_access(
    server_id: str,
    token: dict = Depends(get_current_token),
):
    """Get DCS Olympus URL and credentials for a server.

    Olympus runs behind nginx (OlympusFix) on port 3000 on the public IP.
    Credentials are stored in olympus.json on each VM.
    """
    require_server_access(server_id, token)

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT ip, public_ip, olympus_port FROM servers WHERE id = ?", (server_id,)
    )
    if not rows:
        raise HTTPException(404, f"Server {server_id} not found")

    server = dict(rows[0])
    olympus_port = server["olympus_port"] or 3000

    # Use public_ip for the Olympus URL so external clients can reach it.
    # Fall back to ip if public_ip not set (Tailscale-only deployments).
    access_ip = server["public_ip"] or server["ip"]

    # TODO: Retrieve actual credentials from the VM's olympus.json
    # 1. WinRM to server ip (Tailscale)
    # 2. Read Saved Games\DCS...\Config\olympus.json
    # 3. Extract frontend.gameMasterPassword

    return OlympusAccess(
        server_id=server_id,
        url=f"http://{access_ip}:{olympus_port}",
        username="blue",
        password="",  # TODO: retrieve from VM
    )
