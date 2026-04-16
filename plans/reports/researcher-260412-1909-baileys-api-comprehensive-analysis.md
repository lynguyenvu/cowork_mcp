# Baileys WhatsApp Web API - Comprehensive API Analysis

**Date:** 2026-04-12
**Status:** Complete research report
**Source:** Official Baileys repository, Wiki documentation, NPM package, GitHub examples

---

## Executive Summary

Baileys is a WebSockets-based TypeScript/JavaScript library providing programmatic access to WhatsApp Web API without requiring Selenium or browser automation. Version 7.0.0+ introduces breaking changes; v6.x is stable but deprecated. The library is **production-ready but unofficial** — WhatsApp may break compatibility with system updates.

**Key Stats:**
- 8.9k GitHub stars, 2.9k forks, 2,206+ commits
- MIT licensed, maintained by Rajeh Taher (WhiskeySockets)
- NPM: `@whiskeysockets/baileys` (official), `baileys` (legacy)
- Documentation: https://baileys.wiki (primary), GitHub README (legacy)

---

## 1. AUTHENTICATION & CONNECTION

### Connection Methods

#### A. QR Code Authentication
- User scans QR code from terminal with WhatsApp mobile app
- Acts as secondary client (not primary device)
- Auto-refreshes tokens for reconnection
- **Use case:** Quick setup, ephemeral sessions

```typescript
const { state, saveCreds } = await useMultiFileAuthState('./auth_info_multi')
const sock = makeWASocket({
  auth: state,
  // ... other config
})
```

#### B. Pairing Code Authentication
- Phone number-based 6-8 digit code
- "Connection only with one device" mode
- More stable than QR for production
- **Use case:** Persistent, unattended deployments

#### C. Session Persistence
- `useMultiFileAuthState()` - Saves credentials to filesystem (multi-file format)
- Custom auth state implementations available (SQL, NoSQL, Redis)
- Automatic token refresh via `creds.update` event
- **Required config:** `auth`, `logger`, `getMessage`

### Socket Initialization

```typescript
const sock = makeWASocket({
  // ===== REQUIRED =====
  auth: state,                    // Auth state from useMultiFileAuthState()
  logger: pino(),                 // Logger (default pino)
  getMessage: async (key) => {},  // Function to retrieve stored messages

  // ===== OPTIONAL CONFIG =====
  version: [10, 10, 0],          // WhatsApp Web version (leave default)
  browser: Browsers.macOS('Chrome'),  // Browser UA string
  syncFullHistory: true,          // Emulate desktop for full chat history
  markOnlineOnConnect: false,     // Don't set presence=online on connect
  cachedGroupMetadata: groupMetadata, // Cache to avoid rate limiting

  // ===== UTILITY =====
  fetchLatestBaileysVersion()    // Get current WA Web version
})
```

### Key Events

| Event | Trigger | Usage |
|-------|---------|-------|
| `connection.update` | Connection state changes (qr code, disconnect) | Monitor auth status |
| `creds.update` | Credentials refreshed/updated | Persist to storage |

---

## 2. MESSAGE OPERATIONS

### 2.1 Sending Messages - Core Method

```typescript
await sock.sendMessage(jid, messageContent, options?)
```

**Parameters:**
- `jid` (string): Recipient JID (`'1234567890@s.whatsapp.net'` for user, `'123-456@g.us'` for group)
- `messageContent` (object): Content object (see types below)
- `options` (object): Optional metadata (messageId, timestamp, etc.)

### 2.2 Message Types & Content Objects

#### A. TEXT MESSAGES

```typescript
// Simple text
await sock.sendMessage(jid, { text: 'Hello!' })

// With link preview
await sock.sendMessage(jid, {
  text: 'Check this: https://example.com',
  linkPreview: { title: 'Example', description: '...' }
})

// With mentions
await sock.sendMessage(jid, {
  text: 'Hello @user1 and @user2',
  mentions: ['1234@s.whatsapp.net', '5678@s.whatsapp.net']
})
```

#### B. MEDIA MESSAGES

**Images:**
```typescript
await sock.sendMessage(jid, {
  image: { url: 'https://example.com/pic.jpg' },  // or Buffer, or Stream
  caption: 'Look at this!',
  mimetype: 'image/jpeg',
  jpegThumbnail: base64Data
})
```

**Videos:**
```typescript
await sock.sendMessage(jid, {
  video: { url: 'https://example.com/video.mp4' },  // or Buffer, Stream
  caption: 'Check this video',
  mimetype: 'video/mp4',
  jpegThumbnail: base64Data
})
```

**Audio & Voice Notes:**
```typescript
// Regular audio
await sock.sendMessage(jid, {
  audio: { url: 'https://example.com/audio.mp3' },  // or Buffer, Stream
  mimetype: 'audio/mpeg'
})

// Voice note (PTT)
await sock.sendMessage(jid, {
  audio: buffer,
  mimetype: 'audio/ogg; codecs=opus',
  ptt: true  // Mark as push-to-talk
})
```

**Documents:**
```typescript
await sock.sendMessage(jid, {
  document: { url: 'https://example.com/file.pdf' },  // or Buffer, Stream
  fileName: 'report.pdf',
  mimetype: 'application/pdf',
  caption: 'See attached'
})
```

**Stickers:**
```typescript
await sock.sendMessage(jid, {
  sticker: buffer  // WebP format, no caption allowed
})
```

**GIFs:**
```typescript
await sock.sendMessage(jid, {
  video: buffer,
  gifPlayback: true,  // Special flag for GIF animation
  mimetype: 'video/mp4'
})
```

**View-Once Media (Disappearing):**
```typescript
await sock.sendMessage(jid, {
  image: buffer,
  viewOnce: true  // Media deletes after viewing
})
```

#### C. CONTACT CARDS

```typescript
const vCard = 'BEGIN:VCARD\nVERSION:3.0\nFN:John Doe\nTEL:+1234567890\nEND:VCARD'

await sock.sendMessage(jid, {
  contacts: {
    displayName: 'My Contacts',
    contacts: [{ vcard: vCard }]
  }
})
```

#### D. LOCATIONS

```typescript
await sock.sendMessage(jid, {
  location: {
    degreesLatitude: 24.121231,
    degreesLongitude: 55.1121221
  }
})
```

#### E. POLLS

```typescript
await sock.sendMessage(jid, {
  poll: {
    name: 'Pick your favorite',
    values: ['Option 1', 'Option 2', 'Option 3'],
    selectableCount: 1  // Single or multiple selection
  }
})
```

#### F. REPLY MESSAGES (QUOTED)

```typescript
await sock.sendMessage(jid, {
  text: 'Great point!',
  quoted: originalMessage  // Reference original proto.IWebMessageInfo
})
```

#### G. FORWARDED MESSAGES

```typescript
await sock.relayMessage(jid, originalMessage.message, {
  messageId: originalMessage.key.id
})
```

### 2.3 Message Modification Operations

#### Edit Message (≤15 min window)
```typescript
await sock.sendMessage(jid, {
  text: 'Corrected text',
  edit: originalMessageKey  // IMessageKey from original
})
```

#### Delete Message (≤48 hour window)
```typescript
await sock.sendMessage(jid, {
  delete: originalMessageKey
})
```

#### Add Reaction
```typescript
await sock.sendMessage(jid, {
  react: {
    text: '😂',  // Emoji
    key: messageKey  // IMessageKey to react to
  }
})
```

#### Star/Unstar Message
```typescript
await sock.sendMessage(jid, {
  protocolMessage: {
    key: messageKey,
    type: 'REVOKE'  // or other protocol message types
  }
})
```

### 2.4 Advanced Message Features

**Message Options Parameter:**
```typescript
{
  messageId?: string,           // Custom message ID
  timestamp?: number,           // Custom timestamp (ms)
  quoted?: proto.IWebMessageInfo,  // Reply context
  contextInfo?: {               // Rich context metadata
    quotedMessage?: proto.IMessage,
    mentionedJid?: string[],
    isForwarded?: boolean,
    forwardingScore?: number,
    isStatusPsa?: boolean,
    stanzaId?: string,
    participant?: string,
    remoteJid?: string,
    isBot?: boolean
  },
  caption?: string,             // For media (not stickers)
  jpegThumbnail?: string,      // Base64 JPEG thumbnail
  fileName?: string,            // For documents
  mimetype?: string,            // Media type
  viewOnce?: boolean,           // Disappearing media
  ephemeralExpiration?: number  // Auto-delete duration (seconds)
}
```

### 2.5 Media Handling Notes

- **Streaming:** Baileys never loads full buffer into memory; encrypts media as readable stream
- **Codecs:** Audio requires Opus codec conversion (auto-handled for OGG)
- **Thumbnails:** Optional JPEG thumbnail for faster preview loading
- **URL handling:** Supports HTTP(S) URLs, File streams, and Buffer objects
- **Media deletion:** Deleted from user's view but not WhatsApp servers

---

## 3. MESSAGE RECEIVING & EVENTS

### 3.1 Message Events

#### messages.upsert - New/Synced Messages
```typescript
sock.ev.on('messages.upsert', async ({ type, messages }) => {
  // type: 'notify' (new), 'append' (historical/synced)
  for(const msg of messages) {
    console.log(msg.message.conversation)  // Text content
    console.log(msg.key.remoteJid)         // Sender JID
    console.log(msg.messageTimestamp)      // Timestamp
  }
})
```

**Message Structure:**
- `proto.IWebMessageInfo` object
- Contains: `key`, `message` (proto.IMessage), `messageTimestamp`, `pushName`, `status`
- Message types: `conversation` (text), `extendedTextMessage` (text+metadata), media types, poll, etc.

#### messages.update - Status & Edit Changes
```typescript
sock.ev.on('messages.update', ({ update, key }) => {
  // Update on: message deletion, read receipt, edit, etc.
  for(const { key, update } of event) {
    console.log(update.status)  // 1=delivery, 2=read, 3=played
    console.log(update.edited)  // Edited message timestamp
  }
})
```

#### messages.delete - Message Deletion
```typescript
sock.ev.on('messages.delete', (event) => {
  // Message deleted by sender or admin
  console.log(event)
})
```

#### messages.reaction - Emoji Reactions
```typescript
sock.ev.on('messages.reaction', ({ reaction, key }) => {
  console.log(reaction.text)    // Emoji
  console.log(reaction.fromMe)  // Boolean
})
```

#### message-receipt.update - Delivery Status (Groups)
```typescript
sock.ev.on('message-receipt.update', ({ receipt }) => {
  // Group-specific delivery, view, and playback status
})
```

### 3.2 Chat Events

#### chats.upsert - New Chat
```typescript
sock.ev.on('chats.upsert', (chats) => {
  // New conversation initiated
})
```

#### chats.update - Chat Metadata Changes
```typescript
sock.ev.on('chats.update', (updates) => {
  // Unread count, latest message, etc. update with each message
})
```

#### chats.delete - Chat Deleted
```typescript
sock.ev.on('chats.delete', (keys) => {
  // Chat deleted by user
})
```

### 3.3 Contact & Profile Events

#### contacts.upsert / contacts.update
```typescript
sock.ev.on('contacts.upsert', (contacts) => {
  // New contact added
})

sock.ev.on('contacts.update', (updates) => {
  // Contact profile changed (name, photo)
})
```

#### presence.update - Typing/Online Status
```typescript
sock.ev.on('presence.update', ({ id, presences }) => {
  // presences[jid] = 'available' | 'typing' | 'recording' | 'paused'
})
```

### 3.4 Connection & Credential Events

#### connection.update
```typescript
sock.ev.on('connection.update', (update) => {
  const { connection, lastDisconnect, qr, isNewLogin, auth } = update

  if(qr) {
    // QR code for authentication - display to user
    qrcode.generate(qr, { small: true })
  }

  if(connection === 'open') {
    // Connected and ready
  }

  if(connection === 'close') {
    const reason = lastDisconnect?.error?.output?.statusCode
    if(reason === DisconnectReason.loggedOut) {
      // User logged out
    }
  }
})
```

#### creds.update
```typescript
sock.ev.on('creds.update', saveCreds)
// Save credentials to persistent storage
```

### 3.5 Group Events

#### groups.upsert / groups.update
```typescript
sock.ev.on('groups.upsert', (groups) => {
  // Group joined or group info changed
})
```

#### group-participants.update
```typescript
sock.ev.on('group-participants.update', async ({ id, participants, action }) => {
  // action: 'add' | 'remove' | 'promote' | 'demote'
  // participants: JID array of affected members
})
```

### 3.6 Other Events

#### call - Phone Calls
```typescript
sock.ev.on('call', async (offer) => {
  // offer[0].status = 'offer' | 'accept' | 'decline' | 'timeout'
})
```

#### blocklist.set / blocklist.update
```typescript
sock.ev.on('blocklist.set', (blocks) => {
  // Contact blocked/unblocked
})
```

---

## 4. GROUP MANAGEMENT OPERATIONS

### 4.1 Group Creation & Metadata

#### Create Group
```typescript
const group = await sock.groupCreate(
  'My Awesome Group',  // Subject/name
  ['1234@s.whatsapp.net', '5678@s.whatsapp.net']  // Initial participants
)
console.log(group.gid)  // Returns group ID in format: 123-456@g.us
```

#### Fetch All Groups
```typescript
const groups = await sock.groupFetchAllParticipating()
// Returns: { [gid]: GroupMetadata, ... }
```

#### Get Group Info
```typescript
const metadata = await sock.groupMetadata(jid)
// Returns: GroupMetadata (participants, subject, creation date, etc.)
```

### 4.2 Group Member Management

#### Add Members
```typescript
const added = await sock.groupParticipantsUpdate(
  groupJid,
  ['new1@s.whatsapp.net', 'new2@s.whatsapp.net'],
  'add'
)
// Returns: IDs that were successfully added
```

#### Remove Members
```typescript
await sock.groupParticipantsUpdate(
  groupJid,
  ['user1@s.whatsapp.net'],
  'remove'
)
```

#### Promote to Admin
```typescript
await sock.groupParticipantsUpdate(
  groupJid,
  ['user1@s.whatsapp.net'],
  'promote'
)
```

#### Demote from Admin
```typescript
await sock.groupParticipantsUpdate(
  groupJid,
  ['admin1@s.whatsapp.net'],
  'demote'
)
```

### 4.3 Group Settings

#### Update Subject (Title)
```typescript
await sock.groupUpdateSubject(groupJid, 'New Group Name')
```

#### Update Description
```typescript
await sock.groupUpdateDescription(groupJid, 'Group description text')
```

#### Announcement Mode (Admins Only Post)
```typescript
await sock.groupSettingUpdate(groupJid, 'announcement')
// Or disable:
await sock.groupSettingUpdate(groupJid, 'not_announcement')
```

#### Locked Settings (Admins Only Edit Info)
```typescript
await sock.groupSettingUpdate(groupJid, 'locked')
// Or unlock:
await sock.groupSettingUpdate(groupJid, 'unlocked')
```

#### Member Add Mode
```typescript
await sock.groupMemberAddMode(groupJid, 'all')  // Any member adds
// Or:
await sock.groupMemberAddMode(groupJid, 'admin')  // Admins only add
```

#### Disappearing Messages
```typescript
await sock.groupToggleEphemeral(groupJid, 86400)  // 24 hours (seconds)
// Disable:
await sock.groupToggleEphemeral(groupJid, 0)
```

### 4.4 Group Invitations & Codes

#### Get Invite Code
```typescript
const code = await sock.groupInviteCode(groupJid)
// Example: AhXsdhf...
```

#### Get Invite Info (From Code)
```typescript
const info = await sock.groupGetInviteInfo(inviteCode)
// Returns: { id, subject, size, creation, creator, expiration }
```

#### Revoke Invite Code
```typescript
await sock.groupRevokeInvite(groupJid)
```

#### Request/Approve Join Requests
```typescript
// Enable join approval mode
await sock.groupJoinApprovalMode(groupJid, true)

// Approve pending request
await sock.groupRequestParticipantsUpdate(
  groupJid,
  ['requester1@s.whatsapp.net'],
  'approve'
)

// Decline
await sock.groupRequestParticipantsUpdate(
  groupJid,
  ['requester1@s.whatsapp.net'],
  'reject'
)
```

### 4.5 Group Cleanup

#### Leave Group
```typescript
await sock.groupLeave(groupJid)
```

---

## 5. CONTACT & PROFILE MANAGEMENT

### 5.1 Profile Operations

#### Update Profile Name
```typescript
await sock.updateProfileName('My New Name')
```

#### Update Profile Status
```typescript
await sock.updateProfileStatus('Hello 👋')
```

#### Get Profile Picture URL
```typescript
const url = await sock.profilePictureUrl(jid)
// For high resolution:
const urlHQ = await sock.profilePictureUrl(jid, 'image')
```

#### Set Profile Picture
```typescript
await sock.updateProfilePicture(jidOfPicture)
```

#### Remove Profile Picture
```typescript
await sock.removeProfilePicture()
```

### 5.2 Contact Information

#### Check Contact Exists on WhatsApp
```typescript
const exists = await sock.onWhatsApp('+1234567890', '+9876543210')
// Returns: [{ jid, exists: true|false }, ...]
```

#### Get Business Profile
```typescript
const businessInfo = await sock.getBusinessProfile(jid)
// Returns: { description, category, ... }
```

#### Block/Unblock Contact
```typescript
await sock.updateBlockStatus(jid, 'block')
await sock.updateBlockStatus(jid, 'unblock')
```

### 5.3 Status (Story) Operations

#### Fetch Status Updates
```typescript
sock.ev.on('messages.upsert', ({ messages }) => {
  // Filter messages with status type for story posts
})
```

---

## 6. UTILITY & HELPER METHODS

### Message & Storage

```typescript
// Request placeholder resend (for missed messages)
await sock.requestPlaceholderResend(messageKey)

// Fetch message history on-demand
await sock.fetchMessageHistory(limit, messageKey, timestamp)

// Update missing media
await sock.updateMediaMessage(originalMessage)

// Relay message (forward)
await sock.relayMessage(jid, message, { messageId })

// Generate message ID
const msgId = generateMessageIDV2(userId)

// Process poll votes
getAggregateVotesInPollMessage(pollMessage)
```

### Connection & Version

```typescript
// Fetch latest WhatsApp Web version
const { version, isLatest } = await fetchLatestBaileysVersion()

// Check for new login
socket.ev.on('connection.update', ({ isNewLogin }) => {
  if(isNewLogin) {
    // Fresh login - may need to sync history
  }
})
```

### Type Checking

```typescript
isJidNewsletter(jid)  // Check if JID is newsletter
isJidBroadcast(jid)   // Check if JID is broadcast list
isJidGroup(jid)       // Check if JID is group
isJidUser(jid)        // Check if JID is individual user
```

---

## 7. JID FORMATS

| Type | Format | Example |
|------|--------|---------|
| User | `{phone}@s.whatsapp.net` | `1234567890@s.whatsapp.net` |
| Group | `{timestamp}-{hash}@g.us` | `1234567890-123456@g.us` |
| Broadcast | `{id}@broadcast` | `12345@broadcast` |
| Newsletter | `{id}@newsletter` | `123456@newsletter` |

---

## 8. EVENT SYSTEM SUMMARY

### Event Listening Pattern
```typescript
sock.ev.on('eventName', (data) => {
  // Handle event
})

// Or with error handling:
sock.ev.on('eventName', async (data) => {
  try {
    // Process
  } catch(error) {
    console.error(error)
  }
})

// Multiple listeners
sock.ev.process(async (events) => {
  if(events['messages.upsert']) { ... }
  if(events['chats.update']) { ... }
  if(events['creds.update']) { ... }
})
```

### Complete Event Map
| Event | Trigger | Data Structure |
|-------|---------|-----------------|
| **Connection** | | |
| `connection.update` | Auth/connection changes | `{ connection, qr, lastDisconnect, isNewLogin, auth }` |
| `creds.update` | Credentials refreshed | `{ creds }` |
| **Messages** | | |
| `messages.upsert` | New/synced messages | `{ type, messages[] }` |
| `messages.update` | Edit/delete/status change | `{ key, update }` |
| `messages.delete` | Message deleted | Event data |
| `messages.reaction` | Reaction added/removed | `{ reaction, key }` |
| `message-receipt.update` | Delivery status (groups) | `{ receipt }` |
| **Chats** | | |
| `chats.upsert` | New chat initiated | `chats[]` |
| `chats.update` | Chat metadata changed | `updates[]` |
| `chats.delete` | Chat deleted | `keys[]` |
| **Contacts** | | |
| `contacts.upsert` | New contact added | `contacts[]` |
| `contacts.update` | Contact profile changed | `updates[]` |
| `presence.update` | Online/typing status | `{ id, presences }` |
| **Groups** | | |
| `groups.upsert` | Group joined/info changed | `groups[]` |
| `groups.update` | Group metadata changed | `updates[]` |
| `group-participants.update` | Members added/removed | `{ id, participants, action }` |
| **Other** | | |
| `call` | Incoming/outgoing call | `offers[]` |
| `blocklist.set` | Blocklist initialized | `blocklist[]` |
| `blocklist.update` | Contact blocked/unblocked | `updates[]` |

---

## 9. CONFIGURATION BEST PRACTICES

### Authentication State
```typescript
// Multi-file (default, filesystem)
const { state, saveCreds } = await useMultiFileAuthState('./auth_info')

// Listen for credential updates
sock.ev.on('creds.update', saveCreds)
```

### Logger
```typescript
import pino from 'pino'

const logger = pino({ level: 'debug' })
// Or custom logger with own trace/debug/info/warn/error methods
```

### getMessage Function
```typescript
// Required for message decryption and media
const getMessage = async (key) => {
  if(store) {
    const msg = store.loadMessage(key.remoteJid, key.id)
    return msg?.message
  }
  return proto.Message.fromObject({})
}
```

### Group Metadata Cache
```typescript
// Avoid rate limiting on group sends
const cache = {}
sock.ev.on('groups.update', (updates) => {
  for(const update of updates) {
    delete cache[update.id]  // Invalidate on change
  }
})
```

---

## 10. LIMITATIONS & IMPORTANT NOTES

### Official Limitations
- **Not affiliated with WhatsApp** — No official support, may break with system updates
- **No built-in storage** — Users must implement custom persistence (chats, contacts, messages)
- **Message history** — Desktop client connection required for full chat history sync
- **Media deletion** — Only deletes from user's view; remains on WhatsApp servers
- **Message edit/delete windows** — Edit ≤15 min, Delete ≤48 hours

### Connection Constraints
- **Desktop presence** — Setting presence=online (default) stops mobile push notifications
- **Rate limiting** — Group metadata queries can hit limits without caching
- **Multi-device mode** — One pairing code connection per device only
- **QR expiration** — QR codes expire quickly (~30 seconds)

### Data Handling
- **No chat/contact storage** — Must implement custom store
- **Message memory** — `getMessage` config essential for reply/forward/edit operations
- **Media streaming** — Handles large files efficiently via streams (not buffers)
- **Disappearing content** — view-once media deletes after viewing; status messages auto-delete

### Breaking Changes (v7.0.0+)
- Major API restructuring from v6.x
- Migration guide: https://whiskey.so/migrate-latest
- v6.x support being phased out
- Recommend staying on latest stable v7.x

---

## 11. USE CASE EXAMPLES

### Broadcast Message to Multiple Users
```typescript
const recipients = ['1234@s.whatsapp.net', '5678@s.whatsapp.net']
for(const jid of recipients) {
  await sock.sendMessage(jid, { text: 'Hello!' })
}
```

### Reply to Incoming Message
```typescript
sock.ev.on('messages.upsert', async ({ messages }) => {
  for(const msg of messages) {
    await sock.sendMessage(msg.key.remoteJid, {
      text: 'Thanks for your message!',
      quoted: msg
    })
  }
})
```

### Monitor Group Changes
```typescript
sock.ev.on('group-participants.update', async ({ id, participants, action }) => {
  console.log(`${participants.length} members ${action}ed in ${id}`)
})
```

### Handle Disappeared Messages
```typescript
sock.ev.on('messages.upsert', async ({ messages }) => {
  for(const msg of messages) {
    if(msg.message?.ephemeralMessage) {
      // Auto-delete message after expiration time
    }
  }
})
```

---

## 12. SOURCES & REFERENCES

- [Baileys GitHub Repository](https://github.com/WhiskeySockets/Baileys)
- [Baileys Documentation Wiki](https://baileys.wiki)
- [Baileys NPM Package](https://www.npmjs.com/package/@whiskeysockets/baileys)
- [Example Implementation](https://github.com/WhiskeySockets/Baileys/blob/master/Example/example.ts)
- [Configuration Documentation](https://baileys.wiki/docs/socket/configuration/)
- [Sending Messages Guide](https://baileys.wiki/docs/socket/sending-messages/)
- [Receiving Updates Documentation](https://baileys.wiki/docs/socket/receiving-updates/)
- [Message Handling Guide](https://baileys.wiki/docs/socket/handling-messages/)

---

## 13. UNRESOLVED QUESTIONS

1. **v6 vs v7 migration timeline** — When will v6 reach EOL? Official deprecation timeline not publicly stated.
2. **Rate limiting specifics** — Exact limits for group queries, message sends, and status updates not documented.
3. **Media encryption details** — JPEG thumbnail specifications and encryption methodology not fully detailed.
4. **Custom storage implementations** — Best practices for SQL/Redis backends not thoroughly documented.
5. **Broadcast/Newsletter APIs** — Full API coverage for broadcast lists and newsletter channels incomplete.

