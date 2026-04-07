# DKS_mod - Internal Operations Guide

## Overview

DKS_mod is the Fox3-side REST API for the Digital Kneeboard Simulator (DKS) paid integration. It runs on the .202 customer platform and exposes DCS server data (player events, Tacview files, Olympus access) to DKS via a Cloudflare-tunneled public endpoint.

---

## Credentials & Keys

| Key | Value | Purpose |
|-----|-------|---------|
| Admin Key | `CsT4pNS9rDqAck68FV3xuwXtm5QUYfvJ` | Token management (create/revoke/list API tokens) |
| Secret Key | (auto-generated, stored in env var on .202) | Signs Tacview download URLs and internal tokens |
| Test API Token | `dks_GHpqWj_CU-cc28aMwIKve-hOonuYL5iTpACGH8i4yrQ` | Wildcard access test token |

Environment variables on .202 (set as Machine-level):
- `DKS_ADMIN_KEY` - Admin key for token management endpoints
- `DKS_SECRET_KEY` - Secret key for URL signing (64-char hex)
- `DKS_DB_PATH` - SQLite database path

---

## URLs

| URL | Access | Purpose |
|-----|--------|---------|
| `https://dks.fox3cloud.com` | Public (via Cloudflare tunnel) | Production API for DKS |
| `https://dks.fox3cloud.com/docs` | Public | Swagger UI / interactive API docs |
| `https://dks.fox3cloud.com/openapi.json` | Public | OpenAPI 3.1 spec |
| `http://100.64.0.202:8400` | Mesh only (Tailscale) | Direct access for management/testing |

---

## Service Details

| Item | Value |
|------|-------|
| Machine | 100.64.0.202 (fox3custsystem) |
| Service Name | `DKS-Mod` |
| Managed By | NSSM |
| Install Path | `C:\OpenEdgex86\WRK\Fox3\DKS_mod\` |
| Python | 3.12 (system-wide) |
| Port | 8400 |
| Database | `C:\OpenEdgex86\WRK\Fox3\DKS_mod\dks_mod.db` (SQLite) |
| Logs | `C:\OpenEdgex86\WRK\Fox3\DKS_mod\logs\stdout.log` / `stderr.log` |
| Log Rotation | 10 MB per file |
| Auto-start | Yes (SERVICE_AUTO_START) |
| Crash Recovery | Auto-restart after 10s delay |
| GitHub | `Fox3Luck/DKS_mod` (public) |

---

## Security Architecture

```
Internet --> Cloudflare (WAF/DDoS) --> Tunnel --> localhost:8400 --> DKS_mod
                                                                      |
Tailscale mesh (100.64.0.0/10) -----> port 8400 ------------------> DKS_mod
```

### Layers

1. **Cloudflare** - DDoS protection, WAF, TLS termination, bot mitigation
2. **Windows Firewall** - Port 8400 only accepts:
   - `127.0.0.1` (localhost, for Cloudflare tunnel)
   - `100.64.0.0/10` (Tailscale mesh, for management)
3. **Rate Limiting** (slowapi) - 60 req/min global, 10 req/min on token endpoints
4. **Request Logging** - All requests logged with real client IP (via CF-Connecting-IP header)
5. **API Token Auth** - All data endpoints require `X-API-Key` header with valid token
6. **Admin Key Auth** - Token management requires `X-Admin-Key` header

### Firewall Rules on .202

| Rule Name | Port | Remote Address | Action |
|-----------|------|----------------|--------|
| DKS_mod API - Localhost Only | 8400 | 127.0.0.1 | Allow |
| DKS_mod API - Tailscale Mesh | 8400 | 100.64.0.0/10 | Allow |

### Cloudflare Tunnel

- Tunnel Name: `fox3-stats` (ID: `ca67ea29-...`)
- Config: `C:\Users\Administrator\.cloudflared\config.yml`
- Service: `cloudflared` (Windows service, auto-start)
- Routes: `dks.fox3cloud.com` -> `http://localhost:8400`

---

## Token Management

Tokens are managed via the admin API using the `X-Admin-Key` header.

### Create a token for a customer

```bash
curl -s -X POST https://dks.fox3cloud.com/api/tokens \
  -H "X-Admin-Key: CsT4pNS9rDqAck68FV3xuwXtm5QUYfvJ" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "customer-name",
    "server_ids": ["dcs-v9-66", "dcs-v9-69"],
    "description": "DKS integration for Customer X"
  }'
```

Response includes the raw token (only shown once):
```json
{
  "id": 1,
  "customer_id": "customer-name",
  "token": "dks_ABC123...",
  "server_ids": ["dcs-v9-66", "dcs-v9-69"],
  "description": "DKS integration for Customer X",
  "created_at": "2026-04-07T03:57:21"
}
```

Use `"server_ids": ["*"]` for wildcard access (all servers).

### List active tokens

```bash
curl -s https://dks.fox3cloud.com/api/tokens \
  -H "X-Admin-Key: CsT4pNS9rDqAck68FV3xuwXtm5QUYfvJ"
```

### Revoke a token

```bash
curl -s -X DELETE https://dks.fox3cloud.com/api/tokens/{token_id} \
  -H "X-Admin-Key: CsT4pNS9rDqAck68FV3xuwXtm5QUYfvJ"
```

---

## Service Management (via WinRM or RDP to .202)

```powershell
# Status
nssm status DKS-Mod

# Stop
net stop DKS-Mod

# Start
net start DKS-Mod

# Restart
net stop DKS-Mod && net start DKS-Mod

# View logs (last 50 lines)
Get-Content C:\OpenEdgex86\WRK\Fox3\DKS_mod\logs\stderr.log -Tail 50

# Health check
Invoke-RestMethod http://localhost:8400/api/health
```

### Update to latest code

```powershell
cd C:\OpenEdgex86\WRK\Fox3\DKS_mod
git pull origin master
pip install -r requirements.txt
net stop DKS-Mod
net start DKS-Mod
```

### Scripts (in `scripts\` folder)

| Script | Purpose |
|--------|---------|
| `install.bat` | Full install: deps, NSSM service, firewall, env vars |
| `uninstall.bat` | Remove service and firewall rules (preserves data) |
| `status.bat` | Service status, port check, health endpoint, recent logs |

---

## Database

SQLite at `C:\OpenEdgex86\WRK\Fox3\DKS_mod\dks_mod.db`

### Tables

| Table | Purpose |
|-------|---------|
| `api_tokens` | Issued API tokens (hashed), customer mapping, server scoping |
| `webhooks` | Registered webhook URLs per token |
| `webhook_deliveries` | Delivery history and retry tracking |
| `servers` | Registered DCS server inventory (IP, ports, Tacview paths) |

### Backup

```powershell
Copy-Item C:\OpenEdgex86\WRK\Fox3\DKS_mod\dks_mod.db C:\OpenEdgex86\WRK\Fox3\DKS_mod\dks_mod.db.bak
```

---

## What's Wired Up vs TODO

### Working Now
- API token create/revoke/list (admin)
- Webhook register/unregister/list (per token)
- Webhook event dispatch with HMAC signing and retry
- Rate limiting (60/min global, 10/min auth)
- Request logging with real client IP
- Cloudflare tunnel with TLS
- All API endpoint scaffolding

### Needs VM Wiring
- **gRPC player events**: Connect DCS-gRPC streaming on fleet VMs to event pipeline
- **Tacview file listing/download**: SMB/SSH access to VM Tacview directories
- **Tacview RTT toggle**: Modify TacViewOptions.lua on VMs via SSH or file-based C2
- **Olympus credentials**: Read olympus.json from VMs and return password/URL
- **Server registry**: Populate the `servers` table with actual customer server inventory
