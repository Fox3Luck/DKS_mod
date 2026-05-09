# Fox3 DKS Integration — Developer Quickstart

This guide walks through getting connected and testing each feature end-to-end.

**Base URL:** `https://dks.fox3cloud.com`
**Interactive Docs:** `https://dks.fox3cloud.com/docs`
**Full API Reference:** [DKS-DEVELOPER-GUIDE.md](./DKS-DEVELOPER-GUIDE.md)

---

## Your Test Credentials

```
X-API-Key: dks_ZgOzWku-x60LE4xPNc9DAvRfC-65l9yUwS2m-YYhmd0
```

Scoped to server: **`dcs-v9-66`** (the test DCS server)

---

## Step 1 — Verify connectivity

```bash
curl https://dks.fox3cloud.com/
# {"status":"ok","version":"0.1.0"}
```

---

## Step 2 — Register a webhook

You need a publicly reachable URL on your end. During development, [webhook.site](https://webhook.site) works well for inspecting payloads without standing up a server.

```bash
curl -X POST https://dks.fox3cloud.com/api/webhooks \
  -H "X-API-Key: dks_ZgOzWku-x60LE4xPNc9DAvRfC-65l9yUwS2m-YYhmd0" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-server.com/webhook/fox3",
    "event_types": ["all"],
    "secret": "your-optional-shared-secret"
  }'
```

Response:
```json
{
  "id": 1,
  "url": "https://your-server.com/webhook/fox3",
  "event_types": ["all"],
  "active": true
}
```

Save the `id` — you'll need it to remove the webhook later.

---

## Step 3 — Test a player connect event

Trigger a fake connect event to hit your webhook without needing a real DCS player:

```bash
curl -X POST "https://dks.fox3cloud.com/api/servers/dcs-v9-66/events/connect?player_name=TestPilot&player_ucid=test-ucid-001" \
  -H "X-API-Key: dks_ZgOzWku-x60LE4xPNc9DAvRfC-65l9yUwS2m-YYhmd0"
```

Your webhook will receive:
```json
{
  "event": "connect",
  "server_id": "dcs-v9-66",
  "player_name": "TestPilot",
  "player_ucid": "test-ucid-001",
  "timestamp": "2026-04-07T12:00:00",
  "tacview_url": null
}
```

---

## Step 4 — Test a player disconnect event

```bash
curl -X POST "https://dks.fox3cloud.com/api/servers/dcs-v9-66/events/disconnect?player_name=TestPilot&player_ucid=test-ucid-001" \
  -H "X-API-Key: dks_ZgOzWku-x60LE4xPNc9DAvRfC-65l9yUwS2m-YYhmd0"
```

Disconnect events include a signed Tacview download URL when a recording exists (see Step 6).

---

## Step 5 — Verify webhook signatures

If you provided a `secret`, every webhook POST includes `X-DKS-Signature: sha256=<hex>`.

```python
import hmac, hashlib

def verify_signature(body: bytes, secret: str, header: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", header)
```

> Always verify signatures in production before processing payloads.

---

## Step 6 — Browse Tacview recordings

```bash
curl https://dks.fox3cloud.com/api/servers/dcs-v9-66/tacview \
  -H "X-API-Key: dks_ZgOzWku-x60LE4xPNc9DAvRfC-65l9yUwS2m-YYhmd0"
```

Each file in the response includes a signed `download_url`. These are pre-authenticated — no API key needed to fetch the file:

```bash
curl -O "https://dks.fox3cloud.com/api/servers/dcs-v9-66/tacview/download?file=...&expires=...&sig=..."
```

Signed URLs expire after 1 hour.

---

## Step 7 — Check Tacview RTT status

```bash
curl https://dks.fox3cloud.com/api/servers/dcs-v9-66/tacview/rtt \
  -H "X-API-Key: dks_ZgOzWku-x60LE4xPNc9DAvRfC-65l9yUwS2m-YYhmd0"
```

Response when enabled:
```json
{
  "server_id": "dcs-v9-66",
  "enabled": true,
  "host": "203.0.113.50",
  "port": 42674
}
```

Point Tacview's real-time telemetry client at `host:port` to connect live.

To toggle:
```bash
curl -X POST https://dks.fox3cloud.com/api/servers/dcs-v9-66/tacview/rtt \
  -H "X-API-Key: dks_ZgOzWku-x60LE4xPNc9DAvRfC-65l9yUwS2m-YYhmd0" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

> RTT changes may require a mission restart on the DCS server.

---

## Step 8 — Get Olympus credentials

```bash
curl https://dks.fox3cloud.com/api/servers/dcs-v9-66/olympus \
  -H "X-API-Key: dks_ZgOzWku-x60LE4xPNc9DAvRfC-65l9yUwS2m-YYhmd0"
```

Response:
```json
{
  "server_id": "dcs-v9-66",
  "url": "http://203.0.113.50:3000",
  "username": "blue",
  "password": "..."
}
```

Use this to link into the DCS Olympus web UI (GCI/game master view) for the server.

---

## Cleanup — Remove a webhook

```bash
curl -X DELETE https://dks.fox3cloud.com/api/webhooks/{id} \
  -H "X-API-Key: dks_ZgOzWku-x60LE4xPNc9DAvRfC-65l9yUwS2m-YYhmd0"
```

---

## Rate Limits

- **60 requests/minute** global (per IP)
- Returns `429` when exceeded

---

## Notes

- The test server (`dcs-v9-66`) is a live Fox3 DCS server — real players may be on it during testing.
- Your token is scoped to `dcs-v9-66` only. Production tokens will be scoped to your customer's servers.
- For questions, contact Fox3 directly.
