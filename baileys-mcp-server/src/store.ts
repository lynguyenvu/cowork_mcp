import Database from 'better-sqlite3';
import type { proto, Chat } from '@whiskeysockets/baileys';
import { MAX_MESSAGES_PER_CHAT, MESSAGE_DB_PATH } from './constants.js';

export interface StoredMessage {
  key: proto.IMessageKey;
  message: proto.IMessage | null | undefined;
  messageTimestamp: number | Long | null | undefined;
  pushName?: string | null;
  broadcast?: boolean | null;
}

export interface ChatInfo {
  id: string;
  name?: string;
  unreadCount?: number | null;
  lastMessageTime?: number;
  conversationTimestamp?: number | Long | null;
}

/** SQLite-backed message store for persistence across restarts */
export class MessageStore {
  private db: Database.Database;

  constructor(accountId: string) {
    this.db = new Database(MESSAGE_DB_PATH);
    this.initSchema(accountId);
  }

  /** Initialize SQLite schema for this account */
  private initSchema(accountId: string): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        jid TEXT NOT NULL,
        from_me BOOLEAN NOT NULL,
        timestamp INTEGER NOT NULL,
        message_type TEXT,
        text TEXT,
        raw_message TEXT,
        push_name TEXT,
        broadcast BOOLEAN,
        created_at INTEGER DEFAULT (strftime('%s', 'now'))
      );

      CREATE INDEX IF NOT EXISTS idx_messages_account_jid
        ON messages(account_id, jid);

      CREATE INDEX IF NOT EXISTS idx_messages_account_timestamp
        ON messages(account_id, timestamp);
    `);
  }

  /** Store a message in SQLite */
  storeMessage(accountId: string, msg: StoredMessage): void {
    const jid = msg.key.remoteJid ?? '';
    const id = msg.key.id ?? '';
    const fromMe = msg.key.fromMe ? 1 : 0; // SQLite requires 0/1 for booleans
    const timestamp = Number(msg.messageTimestamp ?? 0);
    const pushName = msg.pushName ?? null;
    const broadcast = msg.broadcast !== undefined && msg.broadcast !== null ? (msg.broadcast ? 1 : 0) : null;

    // Extract message type and text
    const message = msg.message;
    const messageType = message
      ? Object.keys(message).find((k) => k !== 'messageContextInfo') ?? null
      : null;

    const text =
      message?.conversation ??
      message?.extendedTextMessage?.text ??
      message?.imageMessage?.caption ??
      message?.videoMessage?.caption ??
      message?.documentMessage?.caption ??
      null;

    const rawMessage = message ? JSON.stringify(message) : null;

    const stmt = this.db.prepare(`
      INSERT OR REPLACE INTO messages
        (id, account_id, jid, from_me, timestamp, message_type, text, raw_message, push_name, broadcast)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(id, accountId, jid, fromMe, timestamp, messageType, text, rawMessage, pushName, broadcast);

    // Enforce cap: delete oldest messages if exceeding limit per jid
    this.enforceCap(accountId, jid);
  }

  /** Add or update messages for a JID */
  upsertMessages(jid: string, msgs: StoredMessage[], type: 'append' | 'notify' = 'append'): void {
    // Legacy interface - stores to SQLite with placeholder accountId
    // The actual accountId is passed via storeMessage()
    for (const msg of msgs) {
      const accountId = 'default'; // Fallback for legacy calls
      this.storeMessage(accountId, msg);
    }
  }

  /** Delete oldest messages for a JID to maintain cap */
  private enforceCap(accountId: string, jid: string): void {
    const countStmt = this.db.prepare(`
      SELECT COUNT(*) as count FROM messages WHERE account_id = ? AND jid = ?
    `);
    const result = countStmt.get(accountId, jid) as { count: number };
    if (result.count > MAX_MESSAGES_PER_CHAT) {
      const deleteStmt = this.db.prepare(`
        DELETE FROM messages
        WHERE account_id = ? AND jid = ?
        ORDER BY timestamp ASC
        LIMIT ?
      `);
      deleteStmt.run(accountId, jid, result.count - MAX_MESSAGES_PER_CHAT);
    }
  }

  /** Get messages for a JID, optionally filtered by time */
  getMessages(
    accountId: string,
    jid: string,
    limit = 50,
    since?: number,
    until?: number
  ): StoredMessage[] {
    let sql = `
      SELECT id, account_id, jid, from_me, timestamp, message_type, text, raw_message, push_name, broadcast
      FROM messages
      WHERE account_id = ? AND jid = ?
    `;
    const params: (string | number)[] = [accountId, jid];

    if (since != null) {
      sql += ' AND timestamp >= ?';
      params.push(since);
    }
    if (until != null) {
      sql += ' AND timestamp <= ?';
      params.push(until);
    }

    sql += ' ORDER BY timestamp DESC LIMIT ?';
    params.push(limit);

    const stmt = this.db.prepare(sql);
    const rows = stmt.all(...params) as MessageRow[];

    return rows.map((row) => this.rowToStoredMessage(row));
  }

  /** Get all messages across all JIDs, optionally filtered */
  getAllMessages(
    accountId: string,
    limit = 50,
    filterJid?: string,
    since?: number,
    until?: number
  ): StoredMessage[] {
    let sql = `
      SELECT id, account_id, jid, from_me, timestamp, message_type, text, raw_message, push_name, broadcast
      FROM messages
      WHERE account_id = ?
    `;
    const params: (string | number)[] = [accountId];

    if (filterJid) {
      sql += ' AND jid = ?';
      params.push(filterJid);
    }
    if (since != null) {
      sql += ' AND timestamp >= ?';
      params.push(since);
    }
    if (until != null) {
      sql += ' AND timestamp <= ?';
      params.push(until);
    }

    sql += ' ORDER BY timestamp DESC LIMIT ?';
    params.push(limit);

    const stmt = this.db.prepare(sql);
    const rows = stmt.all(...params) as MessageRow[];

    return rows.map((row) => this.rowToStoredMessage(row));
  }

  /** Get recent messages across all chats (for discovery) */
  getRecentMessages(accountId: string, limit = 50): StoredMessage[] {
    return this.getAllMessages(accountId, limit);
  }

  /** Get message by key for reply/react/delete operations */
  getMessage(accountId: string, jid: string, messageId: string): StoredMessage | undefined {
    const stmt = this.db.prepare(`
      SELECT id, account_id, jid, from_me, timestamp, message_type, text, raw_message, push_name, broadcast
      FROM messages
      WHERE account_id = ? AND jid = ? AND id = ?
    `);
    const row = stmt.get(accountId, jid, messageId) as MessageRow | undefined;
    return row ? this.rowToStoredMessage(row) : undefined;
  }

  /** Convert database row to StoredMessage */
  private rowToStoredMessage(row: MessageRow): StoredMessage {
    return {
      key: {
        id: row.id,
        remoteJid: row.jid,
        fromMe: row.from_me === 1,
      },
      message: row.raw_message ? JSON.parse(row.raw_message) : null,
      messageTimestamp: row.timestamp,
      pushName: row.push_name ?? undefined,
      broadcast: row.broadcast === 1,
    };
  }

  /** Upsert chat info (chats table not implemented yet - placeholder) */
  upsertChats(chatList: Partial<ChatInfo>[]): void {
    // Placeholder - chats table could be added separately
  }

  /** Update chat from Baileys Chat object (placeholder) */
  updateChat(chat: Partial<Chat>): void {
    // Placeholder - chats table could be added separately
  }

  /** Get all chats sorted by last activity (placeholder) */
  getChats(): ChatInfo[] {
    // Placeholder - return empty array for now
    return [];
  }

  /** Get chat info by JID (placeholder) */
  getChat(jid: string): ChatInfo | undefined {
    // Placeholder - return undefined for now
    return undefined;
  }

  /** Clear all stored data for an account */
  clear(accountId: string): void {
    const stmt = this.db.prepare('DELETE FROM messages WHERE account_id = ?');
    stmt.run(accountId);
  }

  /** Close database connection */
  close(): void {
    this.db.close();
  }
}

/** Message row from SQLite */
interface MessageRow {
  id: string;
  account_id: string;
  jid: string;
  from_me: number;
  timestamp: number;
  message_type: string | null;
  text: string | null;
  raw_message: string | null;
  push_name: string | null;
  broadcast: number | null;
}

// Per-account store registry — each account ID maps to its own MessageStore instance
const _storeRegistry = new Map<string, MessageStore>();

/** Get or create the MessageStore for a given account ID */
export function getStore(accountId: string): MessageStore {
  let s = _storeRegistry.get(accountId);
  if (!s) {
    s = new MessageStore(accountId);
    _storeRegistry.set(accountId, s);
  }
  return s;
}

/** Remove and clear the store for an account (called on logout) */
export function deleteStore(accountId: string): void {
  const store = _storeRegistry.get(accountId);
  if (store) {
    store.clear(accountId);
    store.close();
    _storeRegistry.delete(accountId);
  }
}

/** Parse relative time string to Unix timestamp
 * Supports: "24h", "7d", "1h", "30m", "1w", etc.
 * Returns: Unix timestamp (seconds) */
export function parseRelativeTime(timeStr: string): number | null {
  const match = timeStr.match(/^(\d+)([hdwm])$/);
  if (!match) return null;

  const value = parseInt(match[1], 10);
  const unit = match[2];
  const now = Math.floor(Date.now() / 1000);

  let seconds = 0;
  switch (unit) {
    case 'h': // hours
      seconds = value * 3600;
      break;
    case 'd': // days
      seconds = value * 86400;
      break;
    case 'w': // weeks
      seconds = value * 604800;
      break;
    case 'm': // minutes
      seconds = value * 60;
      break;
    default:
      return null;
  }

  return now - seconds;
}

export type Long = { toNumber(): number };