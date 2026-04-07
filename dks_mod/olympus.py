"""DCS Olympus credential retrieval."""

import json
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

    Olympus runs behind nginx (OlympusFix) on port 3000.
    Credentials are stored in olympus.json on each VM.
    """
    require_server_access(server_id, token)

    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT ip, olympus_port FROM servers WHERE id = ?", (server_id,)
    )
    if not rows:
        raise HTTPException(404, f"Server {server_id} not found")

    server = dict(rows[0])
    olympus_port = server["olympus_port"] or 3000

    # TODO: Retrieve actual credentials from the VM's olympus.json
    # Implementation pattern:
    # 1. SSH/WinRM to server IP
    # 2. Read %USERPROFILE%\Saved Games\DCS...\Config\olympus.json
    # 3. Extract frontend.gameMasterPassword (plaintext, pre-hash)
    #    OR maintain a credential mapping in the DKS_mod database
    #
    # For customer servers, the Olympus password is typically set during
    # Fox3ServerStart.bat boot sequence and stored in olympus.json.
    #
    # Security note: Olympus grants GCI/game master control.
    # Consider scoping access (read-only blue view vs full control).

    # Placeholder — credentials will come from VM or local DB
    return OlympusAccess(
        server_id=server_id,
        url=f"http://{server['ip']}:{olympus_port}",
        username="blue",  # default Olympus role
        password="",  # TODO: retrieve from VM
    )
