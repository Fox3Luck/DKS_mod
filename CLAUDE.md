# DKS_mod - Fox3 DCS x Digital Kneeboard Simulator Integration API

## What This Is
REST API service that exposes Fox3 DCS server data to Digital Kneeboard Simulator (DKS).
Paid integration — DKS developer consumes these endpoints.

## Tech Stack
- **Python 3.11+** with **FastAPI** (async)
- **SQLite** for tokens, webhooks, audit logs
- **NSSM** for Windows service deployment on .202 machines

## Project Structure
```
dks_mod/
  main.py        - FastAPI app, database init, router mount
  config.py      - Configuration (env vars, paths)
  models.py      - Pydantic request/response schemas
  auth.py        - API token system (generation, validation middleware)
  webhooks.py    - Webhook registry + HMAC-signed event dispatch
  events.py      - Connect/disconnect event pipeline (DCS-gRPC)
  tacview.py     - Tacview file list/download/signed URLs, RTT toggle
  olympus.py     - Olympus credential retrieval
```

## API Endpoints
- `POST /api/tokens` — create API token
- `DELETE /api/tokens/{id}` — revoke token
- `POST /api/webhooks` — register webhook URL
- `DELETE /api/webhooks/{id}` — unregister
- `GET /api/webhooks` — list webhooks
- `GET /api/servers/{id}/tacview` — list Tacview files
- `GET /api/servers/{id}/tacview/{file}` — download (signed URL)
- `POST /api/servers/{id}/tacview/rtt` — enable RTT
- `DELETE /api/servers/{id}/tacview/rtt` — disable RTT
- `GET /api/servers/{id}/tacview/rtt` — RTT status
- `GET /api/servers/{id}/olympus` — get Olympus credentials

## Fleet Communication
- **DCS-gRPC** (port 50051) for player connect/disconnect events
- **SMB/SSH** for Tacview file access
- **File-based C2** via Nextcloud for config changes (RTT toggle)
- **olympus.json** on each VM for Olympus credentials

## Running Locally
```bash
pip install -r requirements.txt
python -m dks_mod.main
```

## Deployment
Windows service via NSSM on .202 customer platform machines.

## GitHub
`Fox3Luck/DKS_mod`
