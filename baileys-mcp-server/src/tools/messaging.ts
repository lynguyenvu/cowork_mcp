import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import type { proto } from '@whiskeysockets/baileys';
import type { StoredMessage } from '../store.js';
import { registry } from '../whatsapp-registry.js';
import { parseRelativeTime } from '../store.js';
import {
  formatError,
  formatJson,
  toUserJid,
  clamp,
  fetchBuffer,
  parseBase64,
  timestampToIso,
} from '../utils/index.js';

/** Shared account param added to every messaging tool */
const accountParam = z
  .string()
  .optional()
  .default('default')
  .describe('WhatsApp account ID (default: "default"). Use whatsapp_list_accounts to see all.');

export function registerMessagingTools(server: McpServer): void {
  // ── whatsapp_send_text ───────────────────────────────────────────────────
  server.tool(
    'whatsapp_send_text',
    `Send a plain text message to a WhatsApp user or group.

Supports optional @mentions by providing a list of JIDs to mention in the message body.
Use the phone number format for mentions in the text: @84987654321

Parameters:
- jid: WhatsApp JID (e.g., '84987654321@s.whatsapp.net' for user, '1234567890-123456@g.us' for group)
- text: Message text content
- mentions: Optional list of JIDs to mention (e.g., ['84987654321@s.whatsapp.net'])
- account: WhatsApp account ID to send from

Returns: Sent message ID and timestamp.`,
    {
      jid: z.string().min(1).describe('Recipient JID or phone number'),
      text: z.string().min(1).describe('Text message content'),
      mentions: z
        .array(z.string())
        .optional()
        .describe('Optional list of JIDs to mention in the message'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ jid, text, mentions, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        const recipientJid = toUserJid(jid);
        const result = await sock.sendMessage(recipientJid, {
          text,
          mentions: mentions?.map(toUserJid),
        });
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                success: true,
                messageId: result?.key?.id,
                timestamp: timestampToIso(result?.messageTimestamp as number | undefined),
                to: recipientJid,
                account,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_send_image ──────────────────────────────────────────────────
  server.tool(
    'whatsapp_send_image',
    `Send an image message to a WhatsApp user or group.

Provide either a public URL or a base64-encoded image string (with optional data URI prefix).
Supports an optional caption text shown below the image.

Parameters:
- jid: Recipient WhatsApp JID or phone number
- url: Public image URL (mutually exclusive with base64)
- base64: Base64-encoded image data, optionally prefixed with 'data:image/jpeg;base64,' (mutually exclusive with url)
- caption: Optional caption text
- mimeType: MIME type when using base64 (default: 'image/jpeg')
- account: WhatsApp account ID to send from

Returns: Sent message ID and timestamp.`,
    {
      jid: z.string().min(1).describe('Recipient JID or phone number'),
      url: z.string().url().optional().describe('Public image URL'),
      base64: z.string().optional().describe('Base64-encoded image data'),
      caption: z.string().optional().describe('Optional image caption'),
      mimeType: z.string().optional().default('image/jpeg').describe('MIME type for base64 input'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ jid, url, base64, caption, mimeType, account }) => {
      try {
        if (!url && !base64) throw new Error('Either url or base64 must be provided');
        const sock = registry.getManager(account).getSock();
        const recipientJid = toUserJid(jid);

        let imageData: Buffer | { url: string };
        if (url) {
          imageData = { url };
        } else {
          imageData = parseBase64(base64!);
        }

        const result = await sock.sendMessage(recipientJid, {
          image: imageData as Parameters<typeof sock.sendMessage>[1] extends { image: infer T }
            ? T
            : never,
          caption,
          mimetype: mimeType,
        });
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                success: true,
                messageId: result?.key?.id,
                timestamp: timestampToIso(result?.messageTimestamp as number | undefined),
                to: recipientJid,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_send_document ───────────────────────────────────────────────
  server.tool(
    'whatsapp_send_document',
    `Send a document/file to a WhatsApp user or group.

Parameters:
- jid: Recipient WhatsApp JID or phone number
- url: Public URL to the document file
- fileName: File name shown to the recipient (e.g., 'report.pdf')
- mimeType: MIME type of the document (e.g., 'application/pdf', 'text/plain')
- caption: Optional caption shown with the document
- account: WhatsApp account ID to send from

Returns: Sent message ID and timestamp.`,
    {
      jid: z.string().min(1).describe('Recipient JID or phone number'),
      url: z.string().url().describe('Public document URL'),
      fileName: z.string().min(1).describe('File name for the recipient'),
      mimeType: z.string().default('application/octet-stream').describe('Document MIME type'),
      caption: z.string().optional().describe('Optional caption'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ jid, url, fileName, mimeType, caption, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        const recipientJid = toUserJid(jid);
        const result = await sock.sendMessage(recipientJid, {
          document: { url },
          fileName,
          mimetype: mimeType,
          caption,
        });
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                success: true,
                messageId: result?.key?.id,
                timestamp: timestampToIso(result?.messageTimestamp as number | undefined),
                to: recipientJid,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_send_audio ──────────────────────────────────────────────────
  server.tool(
    'whatsapp_send_audio',
    `Send an audio message to a WhatsApp user or group.

Set ptt=true to send as a voice note (displayed with waveform UI), false for regular audio file.

Parameters:
- jid: Recipient WhatsApp JID or phone number
- url: Public URL to the audio file (mp3, ogg, m4a, etc.)
- ptt: Send as push-to-talk voice note (default: false)
- mimeType: Audio MIME type (default: 'audio/mp4')
- account: WhatsApp account ID to send from

Returns: Sent message ID and timestamp.`,
    {
      jid: z.string().min(1).describe('Recipient JID or phone number'),
      url: z.string().url().describe('Public audio URL'),
      ptt: z.boolean().optional().default(false).describe('Send as voice note'),
      mimeType: z.string().optional().default('audio/mp4').describe('Audio MIME type'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ jid, url, ptt, mimeType, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        const recipientJid = toUserJid(jid);
        const result = await sock.sendMessage(recipientJid, {
          audio: { url },
          ptt,
          mimetype: mimeType,
        });
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                success: true,
                messageId: result?.key?.id,
                timestamp: timestampToIso(result?.messageTimestamp as number | undefined),
                to: recipientJid,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_send_video ──────────────────────────────────────────────────
  server.tool(
    'whatsapp_send_video',
    `Send a video message to a WhatsApp user or group.

Parameters:
- jid: Recipient WhatsApp JID or phone number
- url: Public URL to the video file (mp4, etc.)
- caption: Optional caption text
- mimeType: Video MIME type (default: 'video/mp4')
- account: WhatsApp account ID to send from

Returns: Sent message ID and timestamp.`,
    {
      jid: z.string().min(1).describe('Recipient JID or phone number'),
      url: z.string().url().describe('Public video URL'),
      caption: z.string().optional().describe('Optional caption'),
      mimeType: z.string().optional().default('video/mp4').describe('Video MIME type'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ jid, url, caption, mimeType, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        const recipientJid = toUserJid(jid);
        const result = await sock.sendMessage(recipientJid, {
          video: { url },
          caption,
          mimetype: mimeType,
        });
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                success: true,
                messageId: result?.key?.id,
                timestamp: timestampToIso(result?.messageTimestamp as number | undefined),
                to: recipientJid,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_send_reaction ───────────────────────────────────────────────
  server.tool(
    'whatsapp_send_reaction',
    `React to a message with an emoji.

Requires the message ID of the target message. Use whatsapp_get_messages to find message IDs.
To remove a reaction, pass an empty string as the emoji.

Parameters:
- jid: Chat JID where the message exists
- messageId: ID of the message to react to
- emoji: Emoji character to react with (e.g., '👍', '❤️', '😂'). Empty string removes reaction.
- fromMe: Whether the target message was sent by you (default: false)
- account: WhatsApp account ID

Returns: Confirmation of reaction sent.`,
    {
      jid: z.string().min(1).describe('Chat JID containing the target message'),
      messageId: z.string().min(1).describe('Message ID to react to'),
      emoji: z.string().describe('Emoji reaction (empty string to remove)'),
      fromMe: z.boolean().optional().default(false).describe('Whether the message was sent by you'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    async ({ jid, messageId, emoji, fromMe, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        const chatJid = toUserJid(jid);
        await sock.sendMessage(chatJid, {
          react: {
            text: emoji,
            key: { remoteJid: chatJid, id: messageId, fromMe },
          },
        });
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                success: true,
                reaction: emoji || '(removed)',
                messageId,
                chat: chatJid,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_send_poll ───────────────────────────────────────────────────
  server.tool(
    'whatsapp_send_poll',
    `Send a poll message to a WhatsApp user or group.

Creates an interactive poll that recipients can vote on. Requires at least 2 options.

Parameters:
- jid: Recipient WhatsApp JID or phone number
- question: Poll question text
- options: List of poll option strings (2-12 options)
- multiSelect: Allow selecting multiple options (default: false)
- account: WhatsApp account ID to send from

Returns: Sent message ID and timestamp.`,
    {
      jid: z.string().min(1).describe('Recipient JID or phone number'),
      question: z.string().min(1).describe('Poll question'),
      options: z.array(z.string().min(1)).min(2).max(12).describe('Poll options (2-12 choices)'),
      multiSelect: z.boolean().optional().default(false).describe('Allow multiple selections'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ jid, question, options, multiSelect, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        const recipientJid = toUserJid(jid);
        const result = await sock.sendMessage(recipientJid, {
          poll: {
            name: question,
            values: options,
            selectableCount: multiSelect ? options.length : 1,
          },
        });
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                success: true,
                messageId: result?.key?.id,
                timestamp: timestampToIso(result?.messageTimestamp as number | undefined),
                to: recipientJid,
                question,
                optionCount: options.length,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_delete_message ──────────────────────────────────────────────
  server.tool(
    'whatsapp_delete_message',
    `Delete a previously sent message.

Can delete for everyone (if within WhatsApp's time limit ~60h) or only for yourself.
Only messages you sent can be deleted for everyone.

Parameters:
- jid: Chat JID where the message exists
- messageId: ID of the message to delete
- deleteForEveryone: Delete for all participants (default: true). Set false to delete only for yourself.
- account: WhatsApp account ID

Returns: Confirmation of deletion.`,
    {
      jid: z.string().min(1).describe('Chat JID containing the message'),
      messageId: z.string().min(1).describe('Message ID to delete'),
      deleteForEveryone: z
        .boolean()
        .optional()
        .default(true)
        .describe('Delete for everyone or just yourself'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: true },
    async ({ jid, messageId, deleteForEveryone, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        const chatJid = toUserJid(jid);
        const key: proto.IMessageKey = { remoteJid: chatJid, id: messageId, fromMe: true };

        if (deleteForEveryone) {
          await sock.sendMessage(chatJid, { delete: key });
        } else {
          await sock.chatModify({ clear: true, lastMessages: [] }, chatJid);
        }

        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({ success: true, messageId, deletedForEveryone: deleteForEveryone }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_get_messages ────────────────────────────────────────────────
  server.tool(
    'whatsapp_get_messages',
    `Get recent messages from SQLite store for a specific account.

Messages are persisted to SQLite and survive server restarts. Use time filters to query messages within a specific time range.

Parameters:
- jid: Optional chat JID to filter messages (e.g., '84987654321@s.whatsapp.net')
- limit: Maximum number of messages to return (1-100, default: 20)
- since: Optional start time filter. Supports relative time strings like "24h", "7d", "1h", "30m" or Unix timestamp
- until: Optional end time filter. Supports relative time strings or Unix timestamp
- account: WhatsApp account ID

Time filter examples:
- "24h" = messages from last 24 hours
- "7d" = messages from last 7 days
- "1h" = messages from last hour
- "1683123456" = messages since Unix timestamp

Returns: Array of message objects with id, from, text, timestamp, and type.`,
    {
      jid: z.string().optional().describe('Optional chat JID to filter messages'),
      limit: z.number().int().min(1).max(100).optional().default(20).describe('Max messages'),
      since: z
        .string()
        .optional()
        .describe('Start time filter: relative (24h, 7d, 1h) or Unix timestamp'),
      until: z
        .string()
        .optional()
        .describe('End time filter: relative (24h, 7d, 1h) or Unix timestamp'),
      account: accountParam,
    },
    { readOnlyHint: true, openWorldHint: false },
    async ({ jid, limit, since, until, account }) => {
      try {
        const s = registry.getManager(account).getStore();
        const safeLimit = clamp(limit ?? 20, 1, 100);
        const filterJid = jid ? toUserJid(jid) : undefined;

        // Parse time filters
        let sinceTs: number | undefined;
        let untilTs: number | undefined;

        if (since) {
          // Try relative time first, then Unix timestamp
          const relative = parseRelativeTime(since);
          if (relative != null) {
            sinceTs = relative;
          } else {
            const parsed = parseInt(since, 10);
            if (!isNaN(parsed) && parsed > 0) {
              sinceTs = parsed;
            }
          }
        }

        if (until) {
          const relative = parseRelativeTime(until);
          if (relative != null) {
            untilTs = relative;
          } else {
            const parsed = parseInt(until, 10);
            if (!isNaN(parsed) && parsed > 0) {
              untilTs = parsed;
            }
          }
        }

        const messages = s.getAllMessages(account, safeLimit, filterJid, sinceTs, untilTs);

        const formatted = messages.map((m: StoredMessage) => {
          const msg = m.message;
          const text =
            msg?.conversation ??
            msg?.extendedTextMessage?.text ??
            msg?.imageMessage?.caption ??
            msg?.videoMessage?.caption ??
            msg?.documentMessage?.caption ??
            null;
          const type = msg
            ? Object.keys(msg).find((k) => k !== 'messageContextInfo') ?? 'unknown'
            : 'unknown';

          return {
            id: m.key.id,
            from: m.key.fromMe ? 'me' : m.key.remoteJid,
            pushName: m.pushName,
            chat: m.key.remoteJid,
            text,
            type,
            timestamp: timestampToIso(m.messageTimestamp),
            fromMe: m.key.fromMe,
          };
        });

        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                account,
                total: formatted.length,
                filters: { jid: filterJid, since: sinceTs, until: untilTs },
                messages: formatted,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_check_number ────────────────────────────────────────────────
  server.tool(
    'whatsapp_check_number',
    `Check if a phone number has an active WhatsApp account.

Queries WhatsApp servers to verify if the given phone number is registered.
Useful before sending a message to verify the number is reachable.

Parameters:
- phone: Phone number with country code (e.g., '84987654321' or '+84987654321')
- account: WhatsApp account ID to use for the query

Returns: JSON with exists (boolean), jid (if registered), and the queried number.`,
    {
      phone: z
        .string()
        .min(7)
        .describe('Phone number with country code (digits only or with + prefix)'),
      account: accountParam,
    },
    { readOnlyHint: true, openWorldHint: true },
    async ({ phone, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        const digits = phone.replace(/\D/g, '');
        const results = await sock.onWhatsApp(digits);
        const result = results?.[0];
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                phone: digits,
                exists: result?.exists ?? false,
                jid: result?.jid ?? null,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );
}

// Suppress unused import warnings for fetchBuffer (used in other potential extensions)
void fetchBuffer;
