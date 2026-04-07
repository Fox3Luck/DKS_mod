# Fox3 DKS Integration - Developer API Reference

## Overview

The Fox3 DKS Integration API provides access to Fox3 DCS server data for the Digital Kneeboard Simulator. This document covers authentication, available endpoints, webhook payloads, and integration patterns.

**Base URL:** `https://dks.fox3cloud.com`
**Interactive Docs:** `https://dks.fox3cloud.com/docs`
**OpenAPI Spec:** `https://dks.fox3cloud.com/openapi.json`

---

## Authentication

All endpoints (except health checks and signed Tacview downloads) require an API token passed via the `X-API-Key` header.

```
X-API-Key: dks_ABC123...
```

Tokens are scoped to specific servers -- a token can only access the servers it was issued for.

### Error responses

| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid API token |
| 403 | Token doesn't have access to the requested server |
| 429 | Rate limit exceeded (60 req/min global) |

---

## Endpoints

### Health & Status

```
GET /
GET /api/health
```

No auth required. Returns:
```json
{"status": "healthy", "version": "0.1.0"}
```

---

### Webhooks

#### Register a webhook

```
POST /api/webhooks
```

**Headers:** `X-API-Key`, `Content-Type: application/json`

**Body:**
```json
{
  "url": "https://your-server.com/webhook/fox3",
  "event_types": ["all"],
  "secret": "optional-shared-secret-for-hmac"
}
```

**Event types:** `"connect"`, `"disconnect"`, `"all"`

**Response (201):**
```json
{
  "id": 1,
  "url": "https://your-server.com/webhook/fox3",
  "event_types": ["all"],
  "created_at": "2026-04-07T03:57:26",
  "active": true
}
```

#### List webhooks

```
GET /api/webhooks
```

**Headers:** `X-API-Key`

**Response:**
```json
{
  "webhooks": [
    {
      "id": 1,
      "url": "https://your-server.com/webhook/fox3",
      "event_types": ["all"],
      "created_at": "2026-04-07T03:57:26",
      "active": true
    }
  ]
}
```

#### Delete a webhook

```
DELETE /api/webhooks/{webhook_id}
```

**Headers:** `X-API-Key`

---

### Webhook Payload Format

When events occur, Fox3 POSTs JSON to your registered webhook URLs.

#### Connect event

```json
{
  "event": "connect",
  "server_id": "dcs-v9-66",
  "player_name": "Maverick",
  "player_ucid": "abc123def456...",
  "timestamp": "2026-04-07T12:00:00",
  "tacview_url": null
}
```

#### Disconnect event

```json
{
  "event": "disconnect",
  "server_id": "dcs-v9-66",
  "player_name": "Maverick",
  "player_ucid": "abc123def456...",
  "timestamp": "2026-04-07T12:45:00",
  "tacview_url": "https://dks.fox3cloud.com/api/servers/dcs-v9-66/tacview/download?file=Tacview-20260407-120000.zip.acmi&expires=1712468700&sig=abc123..."
}
```

The `tacview_url` is a signed, time-limited download URL (expires after 1 hour). No API key is needed to download -- the signature authenticates the request.

#### Webhook signature verification

If you provided a `secret` when registering the webhook, every payload includes an `X-DKS-Signature` header:

```
X-DKS-Signature: sha256=abc123def456...
```

To verify:
```python
import hmac, hashlib

expected = hmac.new(
    your_secret.encode(),
    request_body.encode(),
    hashlib.sha256
).hexdigest()

assert hmac.compare_digest(f"sha256={expected}", request.headers["X-DKS-Signature"])
```

#### Retry behavior

Failed deliveries are retried up to 3 times with exponential backoff. A delivery is considered successful on any 2xx response.

---

### Player Events (Push API)

In addition to webhooks, events can be pushed directly via HTTP:

#### Report a connect

```
POST /api/servers/{server_id}/events/connect?player_name=Maverick&player_ucid=abc123
```

**Headers:** `X-API-Key`

#### Report a disconnect

```
POST /api/servers/{server_id}/events/disconnect?player_name=Maverick&player_ucid=abc123&tacview_url=...
```

**Headers:** `X-API-Key`

These endpoints trigger webhook dispatch to all registered listeners.

---

### Tacview Files

#### List Tacview recordings

```
GET /api/servers/{server_id}/tacview
```

**Headers:** `X-API-Key`

**Response:**
```json
{
  "server_id": "dcs-v9-66",
  "files": [
    {
      "filename": "Tacview-20260407-120000.zip.acmi",
      "size_bytes": 15234567,
      "created_at": "2026-04-07T12:00:00",
      "duration_seconds": 2700,
      "download_url": "https://dks.fox3cloud.com/api/servers/dcs-v9-66/tacview/download?file=...&expires=...&sig=..."
    }
  ]
}
```

#### Download a Tacview file

```
GET /api/servers/{server_id}/tacview/download?file={filename}&expires={timestamp}&sig={signature}
```

**No auth required** -- the signed URL is the authentication. URLs expire after 1 hour.

Returns the raw `.acmi` or `.zip.acmi` file with `Content-Disposition: attachment`.

---

### Tacview Real-Time Telemetry (RTT)

#### Get RTT status

```
GET /api/servers/{server_id}/tacview/rtt
```

**Headers:** `X-API-Key`

**Response:**
```json
{
  "server_id": "dcs-v9-66",
  "enabled": false,
  "host": "203.0.113.50",
  "port": 42674
}
```

When enabled, connect Tacview client to `host:port` for live telemetry.

#### Enable/disable RTT

```
POST /api/servers/{server_id}/tacview/rtt
```

**Headers:** `X-API-Key`, `Content-Type: application/json`

**Body:**
```json
{"enabled": true}
```

Note: Toggling RTT may require a mission restart on the DCS server.

---

### DCS Olympus Access

#### Get Olympus credentials

```
GET /api/servers/{server_id}/olympus
```

**Headers:** `X-API-Key`

**Response:**
```json
{
  "server_id": "dcs-v9-66",
  "url": "http://203.0.113.50:3000",
  "username": "blue",
  "password": "server-specific-password"
}
```

Use these credentials to access the DCS Olympus web UI for the server. Olympus provides GCI/game master capabilities (unit control, battlefield overview, comms).

---

## Rate Limits

| Scope | Limit |
|-------|-------|
| Global (per IP) | 60 requests/minute |
| Token creation | 10 requests/minute |

Exceeding limits returns `429 Too Many Requests`:
```json
{"detail": "Rate limit exceeded. Try again later."}
```

---

## Integration Checklist

1. Obtain API token from Fox3
2. Register webhook URL(s) for connect/disconnect events
3. Implement webhook receiver endpoint on your side
4. (Optional) Implement webhook signature verification
5. Test with a player connecting to a Fox3 DCS server
6. Implement Tacview file browser using list + signed download URLs
7. Implement RTT toggle if needed
8. Implement Olympus access link/embed if needed

---

## Support

For API issues, contact Fox3 directly. For webhook delivery problems, check:
- Is your webhook URL publicly reachable?
- Does your endpoint return a 2xx status code?
- Check `X-DKS-Signature` verification if using a shared secret
