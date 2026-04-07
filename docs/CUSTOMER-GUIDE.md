# Fox3 DCS x DKS Integration - Customer Guide

## What Is This?

Fox3 has partnered with Digital Kneeboard Simulator (DKS) to bring live server integration to your DCS experience. With this integration, DKS can automatically:

- Know when you connect to or disconnect from your Fox3 DCS server
- Provide access to your Tacview recordings for post-flight review
- Enable Tacview Real-Time Telemetry for live flight tracking
- Give you access to DCS Olympus (GCI/game master tool) for your server

---

## Getting Started

### Your API Token

Fox3 will provide you with an API token that looks like this:

```
dks_ABC123def456...
```

This token is unique to you and scoped to your specific Fox3 DCS servers. Keep it secure -- anyone with this token can access your server data.

### Connecting DKS

Enter your API token in the DKS settings under the Fox3 Integration section. DKS will use this token to communicate with your Fox3 servers.

**API Base URL:** `https://dks.fox3cloud.com`

---

## Features

### Player Connect/Disconnect Notifications

When players join or leave your server, DKS receives real-time notifications including:

- Player name and unique ID (UCID)
- Server name
- Timestamp
- On disconnect: a link to download the Tacview recording for that session

### Tacview File Access

Browse and download your server's Tacview recordings directly through DKS:

- Files are listed with date, size, and duration
- Download links are time-limited (1 hour) for security
- Only recordings from your servers are accessible

### Tacview Real-Time Telemetry (RTT)

Enable live Tacview streaming from your server:

- Watch flights in real-time through Tacview
- Can be toggled on/off through DKS
- Note: Enabling/disabling RTT may require a mission restart

### DCS Olympus Access

Access your server's DCS Olympus web interface:

- View the battlefield, manage AI units, act as GCI
- Credentials are provided through the integration
- Access is scoped to your servers only

---

## Webhooks

You can register webhook URLs to receive event notifications. DKS handles this automatically, but if you're building custom integrations:

### Register a webhook

```
POST https://dks.fox3cloud.com/api/webhooks
Header: X-API-Key: your-token-here
Body: {
  "url": "https://your-endpoint.com/webhook",
  "event_types": ["all"]
}
```

### Event types

- `connect` - Player connected to server
- `disconnect` - Player disconnected (includes Tacview download URL)
- `all` - Receive all events

### Webhook payload format

```json
{
  "event": "connect",
  "server_id": "your-server-id",
  "player_name": "PlayerName",
  "player_ucid": "abc123...",
  "timestamp": "2026-04-07T12:00:00",
  "tacview_url": null
}
```

On disconnect events, `tacview_url` contains a signed download link for the session recording.

### Webhook security

If you provide a `secret` when registering, all webhook payloads will include an `X-DKS-Signature` header with an HMAC-SHA256 signature for verification.

---

## Security

- Your API token only grants access to your assigned servers
- Tacview download URLs expire after 1 hour
- All traffic is encrypted via HTTPS (TLS)
- Webhook payloads can be signed with HMAC for verification
- Rate limiting is in place to prevent abuse

---

## Support

Contact Fox3 support for:

- API token issues (lost, compromised, need new token)
- Adding or removing servers from your token
- Integration problems
- Feature requests
