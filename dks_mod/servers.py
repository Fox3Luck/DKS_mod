"""Server registry — manage the DCS server inventory."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dks_mod.auth import verify_admin_key
from dks_mod.database import get_db
from dks_mod.grpc_client import (
    get_stream_status,
    start_stream_for_server,
    stop_stream_for_server,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/servers", tags=["servers"])


class ServerCreate(BaseModel):
    id: str  # e.g. "dcs-v9-66"
    name: str  # e.g. "Fox3 Training Server"
    ip: str  # Tailscale or public IP
    customer_id: str
    grpc_port: int = 50051
    olympus_port: int = 3000
    tacview_path: str | None = None


class ServerInfo(BaseModel):
    id: str
    name: str
    ip: str
    customer_id: str
    grpc_port: int
    olympus_port: int
    tacview_path: str | None
    active: bool
    stream_status: str | None = None


class ServerList(BaseModel):
    servers: list[ServerInfo]


@router.post("", response_model=ServerInfo)
async def register_server(body: ServerCreate, _=Depends(verify_admin_key)):
    """Register a new DCS server (admin only). Starts gRPC stream automatically."""
    db = await get_db()

    # Upsert — update if exists, insert if not
    existing = await db.execute_fetchall(
        "SELECT id FROM servers WHERE id = ?", (body.id,)
    )
    if existing:
        await db.execute(
            "UPDATE servers SET name=?, ip=?, customer_id=?, grpc_port=?, "
            "olympus_port=?, tacview_path=?, active=1 WHERE id=?",
            (body.name, body.ip, body.customer_id, body.grpc_port,
             body.olympus_port, body.tacview_path, body.id)
        )
    else:
        await db.execute(
            "INSERT INTO servers (id, name, ip, customer_id, grpc_port, olympus_port, tacview_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (body.id, body.name, body.ip, body.customer_id, body.grpc_port,
             body.olympus_port, body.tacview_path)
        )
    await db.commit()

    # Start gRPC stream for this server
    await start_stream_for_server(body.id, body.ip, body.grpc_port)

    logger.info("Registered server %s (%s) at %s:%d", body.id, body.name, body.ip, body.grpc_port)
    return ServerInfo(
        id=body.id, name=body.name, ip=body.ip, customer_id=body.customer_id,
        grpc_port=body.grpc_port, olympus_port=body.olympus_port,
        tacview_path=body.tacview_path, active=True, stream_status="running",
    )


@router.get("", response_model=ServerList)
async def list_servers(_=Depends(verify_admin_key)):
    """List all registered servers with stream status (admin only)."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, name, ip, customer_id, grpc_port, olympus_port, tacview_path, active "
        "FROM servers ORDER BY customer_id, id"
    )
    statuses = get_stream_status()
    return ServerList(
        servers=[
            ServerInfo(
                id=r["id"], name=r["name"], ip=r["ip"],
                customer_id=r["customer_id"], grpc_port=r["grpc_port"],
                olympus_port=r["olympus_port"], tacview_path=r["tacview_path"],
                active=bool(r["active"]),
                stream_status=statuses.get(r["id"], "not_started"),
            )
            for r in rows
        ]
    )


@router.delete("/{server_id}")
async def deactivate_server(server_id: str, _=Depends(verify_admin_key)):
    """Deactivate a server and stop its gRPC stream (admin only)."""
    db = await get_db()
    result = await db.execute(
        "UPDATE servers SET active = 0 WHERE id = ?", (server_id,)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(404, f"Server {server_id} not found")

    await stop_stream_for_server(server_id)
    return {"status": "deactivated", "server_id": server_id}


@router.post("/{server_id}/activate")
async def activate_server(server_id: str, _=Depends(verify_admin_key)):
    """Re-activate a server and start its gRPC stream (admin only)."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, ip, grpc_port FROM servers WHERE id = ?", (server_id,)
    )
    if not rows:
        raise HTTPException(404, f"Server {server_id} not found")

    await db.execute("UPDATE servers SET active = 1 WHERE id = ?", (server_id,))
    await db.commit()

    server = dict(rows[0])
    await start_stream_for_server(server["id"], server["ip"], server["grpc_port"])
    return {"status": "activated", "server_id": server_id}
