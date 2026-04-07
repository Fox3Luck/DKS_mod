"""DCS-gRPC StreamEvents client for player connect/disconnect events.

Connects to DCS-gRPC on fleet VMs and streams player events,
dispatching them to registered webhooks via the webhook system.

Based on the proven pattern from Fox3ServerBot/orchestrator/grpc_client.py
and Fox3ServerBot/bot/cogs/stats_commands.py.
"""

import asyncio
import logging
import sys
from pathlib import Path

import grpc

# Add protos directory to path for generated stub imports
_protos_dir = str(Path(__file__).parent.parent / "protos")
if _protos_dir not in sys.path:
    sys.path.insert(0, _protos_dir)

from dcs.mission.v0 import mission_pb2, mission_pb2_grpc

from dks_mod.database import get_db
from dks_mod.webhooks import dispatch_event

logger = logging.getLogger(__name__)

# Track active streaming tasks per server
_stream_tasks: dict[str, asyncio.Task] = {}

# Track connected players per server (id -> {name, ucid})
# Needed because DisconnectEvent only has player id, not name/ucid
_player_sessions: dict[str, dict[int, dict]] = {}


async def _stream_server_events(server_id: str, ip: str, port: int):
    """Long-running task: stream events from a DCS server via gRPC.

    Auto-reconnects on errors with 10s backoff.
    Dispatches connect/disconnect events to registered webhooks.
    """
    address = f"{ip}:{port}"
    logger.info("Starting gRPC stream for server %s at %s", server_id, address)
    _player_sessions.setdefault(server_id, {})

    while True:
        try:
            channel = grpc.aio.insecure_channel(address)
            stub = mission_pb2_grpc.MissionServiceStub(channel)
            stream = stub.StreamEvents(mission_pb2.StreamEventsRequest())

            logger.info("StreamEvents connected for %s", server_id)

            async for response in stream:
                event_type = response.WhichOneof("event")

                if event_type == "connect":
                    evt = response.connect
                    # Cache player info for disconnect lookup
                    _player_sessions[server_id][evt.id] = {
                        "name": evt.name,
                        "ucid": evt.ucid,
                    }
                    logger.info(
                        "Player connect: %s (UCID: %s) on %s",
                        evt.name, evt.ucid, server_id
                    )
                    await dispatch_event("connect", {
                        "event": "connect",
                        "server_id": server_id,
                        "player_name": evt.name,
                        "player_ucid": evt.ucid,
                        "timestamp": _mission_time_to_iso(response.time),
                    })

                elif event_type == "disconnect":
                    evt = response.disconnect
                    # Look up player info from cached session
                    player = _player_sessions[server_id].pop(evt.id, None)
                    player_name = player["name"] if player else f"player_{evt.id}"
                    player_ucid = player["ucid"] if player else ""

                    logger.info(
                        "Player disconnect: %s (reason: %s) from %s",
                        player_name, evt.reason, server_id
                    )
                    # TODO: Generate signed Tacview URL for this session
                    await dispatch_event("disconnect", {
                        "event": "disconnect",
                        "server_id": server_id,
                        "player_name": player_name,
                        "player_ucid": player_ucid,
                        "timestamp": _mission_time_to_iso(response.time),
                        "tacview_url": None,
                    })

                elif event_type == "mission_start":
                    # Clear player sessions on mission restart
                    _player_sessions[server_id].clear()
                    logger.info("Mission started on %s — cleared player sessions", server_id)

            # Stream ended cleanly (server shutdown or mission change)
            logger.warning("StreamEvents ended for %s — reconnecting in 10s", server_id)

        except grpc.aio.AioRpcError as e:
            logger.warning(
                "gRPC error for %s: %s (%s) — reconnecting in 10s",
                server_id, e.code(), e.details()
            )
        except asyncio.CancelledError:
            logger.info("Stream task cancelled for %s", server_id)
            return
        except Exception as e:
            logger.error("Unexpected error streaming %s: %s", server_id, e, exc_info=True)

        # Backoff before reconnecting
        await asyncio.sleep(10)


def _mission_time_to_iso(mission_time: float) -> str:
    """Convert mission time to ISO timestamp.

    Mission time is seconds since mission start, not real-world time.
    We use the current real time instead for webhook payloads.
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def start_all_streams():
    """Start gRPC streaming tasks for all active servers in the database."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, ip, grpc_port FROM servers WHERE active = 1"
    )

    started = 0
    for row in rows:
        sid = row["id"]
        if sid not in _stream_tasks or _stream_tasks[sid].done():
            _stream_tasks[sid] = asyncio.create_task(
                _stream_server_events(sid, row["ip"], row["grpc_port"]),
                name=f"grpc-stream-{sid}",
            )
            started += 1

    logger.info("Started %d gRPC streams (%d total active)", started, len(_stream_tasks))


async def stop_all_streams():
    """Cancel all gRPC streaming tasks."""
    for sid, task in _stream_tasks.items():
        task.cancel()
        logger.info("Cancelled stream for %s", sid)
    _stream_tasks.clear()
    _player_sessions.clear()


async def start_stream_for_server(server_id: str, ip: str, port: int):
    """Start a gRPC stream for a single server (e.g., when a new server is registered)."""
    if server_id in _stream_tasks and not _stream_tasks[server_id].done():
        logger.info("Stream already active for %s", server_id)
        return
    _stream_tasks[server_id] = asyncio.create_task(
        _stream_server_events(server_id, ip, port),
        name=f"grpc-stream-{server_id}",
    )
    logger.info("Started gRPC stream for %s at %s:%d", server_id, ip, port)


async def stop_stream_for_server(server_id: str):
    """Stop the gRPC stream for a single server."""
    task = _stream_tasks.pop(server_id, None)
    if task:
        task.cancel()
        _player_sessions.pop(server_id, None)
        logger.info("Stopped gRPC stream for %s", server_id)


def get_stream_status() -> dict[str, str]:
    """Return status of all gRPC streams."""
    return {
        sid: "running" if not task.done() else "stopped"
        for sid, task in _stream_tasks.items()
    }
