/** Base directory for auth credentials — each account stored in {AUTH_BASE_DIR}/{accountId}/ */
export const AUTH_BASE_DIR = './auth_info';

/** Default account ID used when no account is specified */
export const DEFAULT_ACCOUNT = 'default';

/** SQLite database path for message persistence (configurable via env) */
export const MESSAGE_DB_PATH = process.env.MESSAGE_DB_PATH ?? './messages.db';

/** Maximum messages stored per chat JID in memory store */
export const MAX_MESSAGES_PER_CHAT = 1000;

/** Maximum characters in list responses to avoid token overflow */
export const CHARACTER_LIMIT = 25000;

/** Reconnection delay in milliseconds */
export const RECONNECT_DELAY_MS = 3000;

/** Maximum reconnection attempts before giving up */
export const MAX_RECONNECT_ATTEMPTS = 5;

/** WhatsApp JID suffixes */
export const JID_USER_SUFFIX = '@s.whatsapp.net';
export const JID_GROUP_SUFFIX = '@g.us';
export const JID_BROADCAST_SUFFIX = '@broadcast';
