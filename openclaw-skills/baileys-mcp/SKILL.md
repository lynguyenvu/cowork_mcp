# Baileys WhatsApp MCP Skill for OpenClaw

## Description

Send and manage WhatsApp messages, groups, and contacts via the Baileys library.
Enables OpenClaw to automate WhatsApp messaging workflows for business operations.

> **Unofficial API**: Baileys reverse-engineers WhatsApp Web. Requires a real WhatsApp account.

## First-Time Setup (QR Auth)

On first launch, the MCP server needs WhatsApp authentication:

1. Start the stack: `docker compose up -d`
2. Get the QR code: `GET http://localhost:8769/qr?account=default`
3. Open WhatsApp on your phone → **Linked Devices** → **Link a Device** → scan QR
4. Done — credentials auto-saved, reconnects on restart

To check current status: `GET http://localhost:8769/health`

## Capabilities

- **Messaging**: Send text, images, documents, audio, video, polls, reactions
- **Group Management**: Create/modify groups, manage participants, get invite links
- **Contacts**: Check if phone numbers have WhatsApp
- **Message History**: Retrieve messages by time range (SQLite persisted)
- **Multi-Account**: Support multiple WhatsApp numbers via WHATSAPP_ACCOUNTS env

## Configuration

No API key required. Authentication is via QR code scan (one-time per device).

```env
# Multi-account setup (optional)
WHATSAPP_ACCOUNTS=default,work,sales

# Database path (optional)
MESSAGE_DB_PATH=./messages.db
```

## Tools (22 total)

### Connection Tools
- `whatsapp_list_accounts` — List all configured accounts + statuses
- `whatsapp_get_status` — Connection status, phone number, QR code
  - `account?`: Account ID (default: "default")
- `whatsapp_logout` — Logout and clear saved credentials
  - `account?`: Account ID

### Messaging Tools
- `whatsapp_send_text` — Send text message
  - `jid`: Phone number or JID
  - `text`: Message content
  - `mentions?`: Array of JIDs to @mention
  - `account?`: Account ID
- `whatsapp_send_image` — Send image from URL/base64
  - `jid`, `url` | `base64`, `caption?`, `mimeType?`
- `whatsapp_send_document` — Send document
  - `jid`, `url`, `fileName`, `mimeType?`, `caption?`
- `whatsapp_send_audio` — Send audio
  - `jid`, `url`, `ptt?` (voice note), `mimeType?`
- `whatsapp_send_video` — Send video
  - `jid`, `url`, `caption?`, `mimeType?`
- `whatsapp_send_reaction` — React to message
  - `jid`, `messageId`, `emoji`, `fromMe?`
- `whatsapp_send_poll` — Send poll
  - `jid`, `question`, `options` (array), `multiSelect?`
- `whatsapp_delete_message` — Delete sent message (48hr window)
  - `jid`, `messageId`, `deleteForEveryone?`
- `whatsapp_get_messages` — Get messages by time range
  - `jid?`: Filter by chat
  - `limit?`: Max results (1-100)
  - `since?`: Time filter ("24h", "7d", Unix ts)
  - `until?`: Time filter
  - `account?`: Account ID
- `whatsapp_check_number` — Check if phone has WhatsApp
  - `phone`: Phone number with country code
  - `account?`: Account ID

### Group Tools
- `whatsapp_list_groups` — List all joined groups
- `whatsapp_get_group_info` — Group details + participants
  - `jid`: Group JID
- `whatsapp_create_group` — Create new group
  - `name`, `participants` (array)
- `whatsapp_add_participants` — Add members
  - `jid`, `participants`
- `whatsapp_remove_participants` — Remove members
  - `jid`, `participants`
- `whatsapp_update_group_subject` — Rename group
  - `jid`, `subject`
- `whatsapp_update_group_description` — Update description
  - `jid`, `description`
- `whatsapp_get_invite_link` — Get invite link
  - `jid`, `reset?` (revoke old link)
- `whatsapp_leave_group` — Leave group
  - `jid`

## Time Filters (NEW)

Messages now persisted in SQLite — survive server restart!

| Format | Example | Description |
|--------|---------|-------------|
| Relative | `"24h"` | Last 24 hours |
| Relative | `"7d"` | Last 7 days |
| Relative | `"1h"` | Last 1 hour |
| Relative | `"30m"` | Last 30 minutes |
| Unix ts | `1712800000` | Absolute timestamp |

Example:
```
whatsapp_get_messages jid=84987654321 since="24h" limit=50
```

## JID Formats

| Type | Format | Example |
|------|--------|---------|
| User | `{phone}@s.whatsapp.net` | `84987654321@s.whatsapp.net` |
| Group | `{ts}-{hash}@g.us` | `1234567890-123456@g.us` |

**Tools accept bare phone numbers** — auto-converted to user JID.

Vietnam numbers: remove leading 0, add 84 (0987654321 → 84987654321)

## Usage Examples

```
# Check connection first!
whatsapp_list_accounts
whatsapp_get_status account=default

# Send text
whatsapp_send_text jid=84987654321 text="Hello from AI!"

# Send image
whatsapp_send_image jid=84987654321 url="https://example.com/photo.jpg" caption="Check this"

# Get messages from last 24h
whatsapp_get_messages jid=84987654321 since="24h" limit=20

# Check if number has WhatsApp
whatsapp_check_number phone=84987654321

# Group operations
whatsapp_list_groups
whatsapp_get_group_info jid=1234567890-123456@g.us
whatsapp_create_group name="Team" participants=["84987654321"]
whatsapp_add_participants jid=1234567890-123456@g.us participants=["84911111111"]
```

## Endpoints

| Service | Port | URL |
|---------|------|-----|
| MCP Server | 8769 | `http://localhost:8769/mcp` |
| QR Code | 8769 | `GET http://localhost:8769/qr?account={id}` |
| Health | 8769 | `GET http://localhost:8769/health` |

## Important Notes

| Issue | Note |
|-------|------|
| Edit window | Messages editable within 15 min |
| Delete window | Messages deletable within 48 hr |
| Rate limiting | Avoid bulk sending → WhatsApp may block |
| Persistence | SQLite DB — messages survive restart ✅ |
| Max storage | 1000 msgs/chat auto-cap |
| Credentials | Docker volume `baileys-auth` — persists |

## License

MIT
