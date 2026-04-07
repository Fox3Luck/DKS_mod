"""Connect/disconnect event pipeline.

Connects to DCS-gRPC on each registered server VM to stream player events,
then dispatches them to registered webhooks.
"""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends

from dks_mod.auth import get_current_token, require_server_access
from dks_mod.database import get_db
from dks_mod.webhooks import dispatch_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/servers", tags=["events"])

# Track active gRPC listeners per server
_listeners: dict[str, asyncio.Task] = {}


async def _grpc_player_listener(server_id: str, ip: str, port: int):
    """Long-running task that streams player events from DCS-gRPC.

    Uses the hook.MissionEvent or similar streaming RPC.
    This is a placeholder — actual gRPC proto integration depends on
    the DCS-gRPC version deployed on Fox3 fleet.
    """
    logger.info("Starting gRPC player listener for server %s at %s:%d", server_id, ip, port)

    while True:
        try:
            # TODO: Import generated gRPC stubs from DCS-gRPC protos
            # For now, this outlines the integration pattern:
            #
            # channel = grpc.aio.insecure_channel(f"{ip}:{port}")
            # stub = hook_pb2_grpc.HookServiceStub(channel)
            # stream = stub.StreamEvents(hook_pb2.StreamEventsRequest(
            #     event_type=hook_pb2.EVENT_PLAYER_CONNECT
            # ))
            # async for event in stream:
            #     await _handle_player_event(server_id, event)

            logger.info("gRPC listener for %s: waiting for implementation with DCS-gRPC protos", server_id)
            await asyncio.sleep(30)

        except Exception as e:
            logger.error("gRPC listener error for %s: %s", server_id, e)
            await asyncio.sleep(10)  # reconnect delay


async def handle_player_connect(server_id: str, player_name: str, player_ucid: str):
    """Process a player connect event and dispatch to webhooks."""
    event_payload = {
        "event": "connect",
        "server_id": server_id,
        "player_name": player_name,
        "player_ucid": player_ucid,
        "timestamp": datetime.utcnow().isoformat(),
    }
    logger.info("Player connect: %s on %s", player_name, server_id)
    await dispatch_event("connect", event_payload)


async def handle_player_disconnect(
    server_id: str, player_name: str, player_ucid: str, tacview_url: str | None = None
):
    """Process a player disconnect event and dispatch to webhooks."""
    event_payload = {
        "event": "disconnect",
        "server_id": server_id,
        "player_name": player_name,
        "player_ucid": player_ucid,
        "timestamp": datetime.utcnow().isoformat(),
        "tacview_url": tacview_url,
    }
    logger.info("Player disconnect: %s from %s", player_name, server_id)
    await dispatch_event("disconnect", event_payload)


# --- HTTP endpoint for manual/push-based event ingestion ---
# Allows VMs to POST events directly instead of relying on gRPC polling

@router.post("/{server_id}/events/connect")
async def post_connect_event(
    server_id: str,
    player_name: str,
    player_ucid: str,
    token: dict = Depends(get_current_token),
):
    """Ingest a connect event (push from VM or admin)."""
    require_server_access(server_id, token)
    await handle_player_connect(server_id, player_name, player_ucid)
    return {"status": "dispatched"}


@router.post("/{server_id}/events/disconnect")
async def post_disconnect_event(
    server_id: str,
    player_name: str,
    player_ucid: str,
    tacview_url: str | None = None,
    token: dict = Depends(get_current_token),
):
    """Ingest a disconnect event (push from VM or admin)."""
    require_server_access(server_id, token)
    await handle_player_disconnect(server_id, player_name, player_ucid, tacview_url)
    return {"status": "dispatched"}


async def start_listeners():
    """Start gRPC listeners for all active servers."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, ip, grpc_port FROM servers WHERE active = 1"
    )
    for row in rows:
        sid = row["id"]
        if sid not in _listeners or _listeners[sid].done():
            _listeners[sid] = asyncio.create_task(
                _grpc_player_listener(sid, row["ip"], row["grpc_port"])
            )
    logger.info("Started %d gRPC listeners", len(_listeners))


async def stop_listeners():
    """Stop all gRPC listeners."""
    for task in _listeners.values():
        task.cancel()
    _listeners.clear()
