# Baileys WhatsApp MCP Skill for OpenClaw

## Description

Send and manage WhatsApp messages, groups, and contacts via the Baileys library.
Enables OpenClaw to automate WhatsApp messaging workflows for business operations.

> **Unofficial API**: Baileys reverse-engineers WhatsApp Web. Requires a real WhatsApp account.

## First-Time Setup (QR Auth)

On first launch, the MCP server needs WhatsApp authentication:

1. Start the stack: `docker compose up -d`
2. Get the QR code: `GET http://localhost:8770/qr`
3. Open WhatsApp on your phone → **Linked Devices** → **Link a Device** → scan QR
4. Done — credentials auto-saved, reconnects on restart

To check current status: `GET http://localhost:8770/health`

## Capabilities

- **Messaging**: Send text, images, documents, audio, video, polls, reactions
- **Group Management**: Create/modify groups, manage participants, get invite links
- **Contacts**: Check if phone numbers have WhatsApp
- **Message History**: Retrieve recent messages from in-memory store

## Configuration

No API key required. Authentication is via QR code scan (one-time per device).

```env
# No required env vars for basic operation
# Optional overrides:
# BAILEYS_MCP_URL=http://baileys-mcp:8769  (set in docker-compose)
# GATEWAY_PORT=8770
```

## Tools

### Connection Tools
- `whatsapp_get_status` — Connection status, phone number, QR code data
- `whatsapp_logout` — Logout and clear saved credentials

### Messaging Tools
- `whatsapp_send_text` — Send text message to user/group
  - `jid`: Recipient (phone number or JID)
  - `text`: Message content
  - `mentions?`: Optional array of JIDs to @mention
- `whatsapp_send_image` — Send image from URL or base64
  - `jid`, `url` | `base64`, `caption?`, `mimeType?`
- `whatsapp_send_document` — Send document from URL
  - `jid`, `url`, `fileName?`, `caption?`, `mimeType?`
- `whatsapp_send_audio` — Send audio from URL
  - `jid`, `url`, `mimeType?`
- `whatsapp_send_video` — Send video from URL
  - `jid`, `url`, `caption?`
- `whatsapp_send_reaction` — React to a message
  - `jid`, `messageId`, `emoji` (e.g. "👍", "❤️", "" to remove)
- `whatsapp_send_poll` — Send a poll
  - `jid`, `question`, `options` (array), `allowMultiple?`
- `whatsapp_delete_message` — Delete a sent message (within 48hr)
  - `jid`, `messageId`
- `whatsapp_get_messages` — Get recent messages from store
  - `jid?` (filter), `limit?` (default 20)
- `whatsapp_check_number` — Check if phones have WhatsApp
  - `phones`: Array of phone numbers (e.g. ["84987654321"])

### Group Tools
- `whatsapp_list_groups` — List all joined groups
- `whatsapp_get_group_info` — Get group details + participant list
  - `jid`: Group JID (e.g. "1234567890-123456@g.us")
- `whatsapp_create_group` — Create a new group
  - `name`, `participants` (array of phones/JIDs)
- `whatsapp_add_participants` — Add members to group
  - `jid`, `participants`
- `whatsapp_remove_participants` — Remove members from group
  - `jid`, `participants`
- `whatsapp_update_group_subject` — Rename group
  - `jid`, `subject`
- `whatsapp_update_group_description` — Update group description
  - `jid`, `description`
- `whatsapp_get_invite_link` — Get group invite link
  - `jid`
- `whatsapp_leave_group` — Leave a group
  - `jid`

## JID Formats

| Type | Format | Example |
|------|--------|---------|
| User | `{phone}@s.whatsapp.net` | `84987654321@s.whatsapp.net` |
| Group | `{ts}-{hash}@g.us` | `1234567890-123456@g.us` |

Tools also accept bare phone numbers — auto-converted to user JID.

## Usage Examples

```
Send "Hello team!" to group 1234567890-123456@g.us
Send image from https://example.com/photo.jpg to 84987654321
Check if 84987654321 and 84912345678 have WhatsApp
List all WhatsApp groups
Get invite link for group 1234567890-123456@g.us
Add 84911111111 to group 1234567890-123456@g.us
```

## Endpoints

| Service | Port | URL |
|---------|------|-----|
| Gateway (REST) | 8770 | `http://localhost:8770` |
| MCP Server (HTTP) | 8769 | `http://localhost:8769/mcp` |
| QR Code | 8770 | `GET http://localhost:8770/qr` |
| Health | 8770 | `GET http://localhost:8770/health` |

## Important Notes

- **Edit window**: Messages can only be edited within 15 minutes
- **Delete window**: Messages can only be deleted within 48 hours
- **Rate limiting**: Avoid bulk sending — WhatsApp may temporarily block accounts
- **Storage**: Recent messages kept in-memory only; lost on restart
- **Credentials**: Stored in Docker volume `baileys-auth` — persists across restarts

## License

MIT
