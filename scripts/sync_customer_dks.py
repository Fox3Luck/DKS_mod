#!/usr/bin/env python3
"""
sync_customer_dks.py -- Wire the cust-servers.DKS toggle in Fox3CustomerWindow
to actual DKS_mod state.

Fired from the SAVE handler in Fox3CustomerWindow5-5.w via OS-COMMAND, the same
pattern as Fox3ServerBot/scripts/cancel_server.py.

Behavior:
  --enable
    1. Upsert the server in DKS_mod servers table (POST /api/servers).
       This also starts the gRPC StreamEvents task for the server.
    2. Find an active token for this customer (GET /api/tokens, filter).
       - If found and already includes this server_id -> no-op.
       - If found and missing -> PATCH /api/tokens/{id} to add it (token
         value preserved, customer's DKS config keeps working).
       - If none -> POST /api/tokens to mint one. Raw token written to
         C:\\tmp\\dks_token_<cust-num>.txt for the operator to hand off.

  --disable
    1. DELETE /api/servers/{id} (deactivates + stops gRPC stream).
    2. Remove server_id from any token that has it (PATCH).
       If the resulting list is empty, revoke the token entirely.

Idempotent: safe to fire on every save.

Usage:
    python sync_customer_dks.py --server-num G2-141 --cust-num 12345 \
        --customer-name "John Smith" --public-ip 51.195.85.141 \
        (--enable | --disable)

The customer-window OS-COMMAND redirects stdout/stderr to
  C:\\tmp\\dks_<server-num>.log
"""

import argparse
import json
import os
import sys
from datetime import datetime

import urllib.request
import urllib.error

BASE_URL    = "http://127.0.0.1:8400/api"
ADMIN_KEY   = os.environ.get("DKS_ADMIN_KEY", "CsT4pNS9rDqAck68FV3xuwXtm5QUYfvJ")
TMP_DIR     = r"C:\tmp"


def log(msg: str) -> None:
    print(f"[{datetime.utcnow().isoformat(timespec='seconds')}Z] {msg}", flush=True)


def http(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    url = BASE_URL + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Admin-Key", ADMIN_KEY)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body_text)
        except Exception:
            return e.code, {"detail": body_text}


def server_id_for(server_num: str) -> str:
    return f"dcs-{server_num.lower()}"


def parse_dense(server_num: str) -> tuple[bool, str | None, int]:
    """Return (is_dense, tailscale_host, grpc_port).

    Dense = 3-segment server_num (e.g. G2-191-851). Standalone = 2-segment
    (e.g. V9-66, G2-141). Per memory: dense gRPC port = 5 + zfill(fox3_id, 4).
    """
    parts = server_num.split("-")
    if len(parts) == 3:
        machine = "-".join(parts[:2])              # G2-191
        fox3_id = parts[2]                         # 851
        try:
            grpc_port = int(f"5{int(fox3_id):04d}")  # 50851
        except ValueError:
            grpc_port = 50051
        return True, f"dcs-{machine.lower()}", grpc_port
    return False, None, 50051


def tacview_path_for(server_num: str, is_dense: bool) -> str:
    if is_dense:
        fox3_id = int(server_num.rsplit("-", 1)[1])
        # Saved Games folder may be Fox3-851 or Fox3-0851 -- callers handle both
        return rf"C:\Users\luck\Saved Games\Fox3-{fox3_id:04d}\Tacview"
    return r"C:\Users\luck\Saved Games\DCS.openbeta_server\Tacview"


def find_token_for_customer(customer_id: str) -> dict | None:
    status, body = http("GET", "/tokens")
    if status != 200 or not isinstance(body, list):
        log(f"WARN: list tokens returned {status}: {body}")
        return None
    matches = [t for t in body if t.get("customer_id") == customer_id]
    if not matches:
        return None
    matches.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return matches[0]


def write_token_file(cust_num: str, token: str, server_ids: list[str], description: str) -> str:
    os.makedirs(TMP_DIR, exist_ok=True)
    path = os.path.join(TMP_DIR, f"dks_token_{cust_num}.txt")
    with open(path, "w", encoding="ascii") as f:
        f.write(f"DKS API Token for customer {cust_num}\n")
        f.write(f"Created: {datetime.utcnow().isoformat(timespec='seconds')}Z\n")
        f.write(f"Description: {description}\n")
        f.write(f"Servers: {', '.join(server_ids)}\n")
        f.write(f"\nToken (give to customer):\n{token}\n")
        f.write(f"\nBase URL: https://dks.fox3cloud.com\n")
    return path


def do_enable(args) -> int:
    sid          = server_id_for(args.server_num)
    is_dense, dense_host, grpc_port = parse_dense(args.server_num)
    tailscale_host = dense_host if is_dense else f"dcs-{args.server_num.lower()}"
    tv_path        = tacview_path_for(args.server_num, is_dense)
    cust_id        = str(args.cust_num)

    log(f"ENABLE server_id={sid} tailscale={tailscale_host} grpc_port={grpc_port} dense={is_dense}")

    # 1. Upsert server
    name = (
        f"{args.customer_name} - {args.server_num}".strip(" -")
        if args.customer_name
        else f"Customer #{cust_id} - {args.server_num}"
    )
    body = {
        "id":            sid,
        "name":          name,
        "ip":            tailscale_host,
        "public_ip":     args.public_ip or None,
        "customer_id":   cust_id,
        "grpc_port":     grpc_port,
        "olympus_enabled": False,
        "olympus_port":  3000,
        "tacview_path":  tv_path,
    }
    status, resp = http("POST", "/servers", body)
    if status >= 300:
        log(f"ERROR: server upsert failed {status}: {resp}")
        return 2
    log(f"  server upserted: {resp.get('id')}")

    # 2. Token: find or create, then patch if needed
    existing = find_token_for_customer(cust_id)
    if existing is None:
        description = (
            f"Auto-issued for {args.customer_name}".strip()
            if args.customer_name
            else f"Auto-issued for customer #{cust_id}"
        )
        body = {
            "customer_id":  cust_id,
            "server_ids":   [sid],
            "description":  description,
        }
        status, resp = http("POST", "/tokens", body)
        if status >= 300:
            log(f"ERROR: token create failed {status}: {resp}")
            return 3
        path = write_token_file(cust_id, resp["token"], resp["server_ids"], resp["description"])
        log(f"  token CREATED id={resp['id']}, raw value written to {path}")
        return 0

    server_ids = list(existing.get("server_ids") or [])
    if "*" in server_ids:
        log(f"  token id={existing['id']} has wildcard, no patch needed")
        return 0
    if sid in server_ids:
        log(f"  token id={existing['id']} already includes {sid}, no-op")
        return 0
    server_ids.append(sid)
    status, resp = http("PATCH", f"/tokens/{existing['id']}", {"server_ids": server_ids})
    if status >= 300:
        log(f"ERROR: token patch failed {status}: {resp}")
        return 4
    log(f"  token id={existing['id']} patched: server_ids={server_ids}")
    return 0


def do_disable(args) -> int:
    sid     = server_id_for(args.server_num)
    cust_id = str(args.cust_num)

    log(f"DISABLE server_id={sid} customer={cust_id}")

    # 1. Deactivate server
    status, resp = http("DELETE", f"/servers/{sid}")
    if status == 404:
        log(f"  server {sid} not registered (already absent)")
    elif status >= 300:
        log(f"WARN: server deactivate returned {status}: {resp}")
    else:
        log(f"  server {sid} deactivated")

    # 2. Patch token to remove this server
    existing = find_token_for_customer(cust_id)
    if existing is None:
        log("  no active token for customer, nothing to patch")
        return 0

    server_ids = list(existing.get("server_ids") or [])
    if "*" in server_ids:
        log(f"  token id={existing['id']} is wildcard, leaving as-is")
        return 0
    if sid not in server_ids:
        log(f"  token id={existing['id']} did not include {sid}, no-op")
        return 0
    server_ids.remove(sid)
    if not server_ids:
        status, resp = http("DELETE", f"/tokens/{existing['id']}")
        if status >= 300:
            log(f"WARN: token revoke returned {status}: {resp}")
        else:
            log(f"  token id={existing['id']} REVOKED (last server removed)")
        return 0
    status, resp = http("PATCH", f"/tokens/{existing['id']}", {"server_ids": server_ids})
    if status >= 300:
        log(f"WARN: token patch returned {status}: {resp}")
    else:
        log(f"  token id={existing['id']} patched: server_ids={server_ids}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--server-num", required=True, help="e.g. V9-66, G2-141, G2-191-851")
    p.add_argument("--cust-num",   required=True, help="Fox3 customer number")
    p.add_argument("--customer-name", default="", help="Display name for description/server name")
    p.add_argument("--public-ip", default="", help="Public IP (stored on server row, optional)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--enable",  action="store_true")
    g.add_argument("--disable", action="store_true")
    args = p.parse_args()

    log(f"sync_customer_dks: server={args.server_num} cust={args.cust_num} "
        f"action={'enable' if args.enable else 'disable'}")
    try:
        return do_enable(args) if args.enable else do_disable(args)
    except Exception as e:
        log(f"FATAL: {type(e).__name__}: {e}")
        return 99


if __name__ == "__main__":
    sys.exit(main())
