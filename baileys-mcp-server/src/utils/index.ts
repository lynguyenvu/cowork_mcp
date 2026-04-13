import { CHARACTER_LIMIT, JID_GROUP_SUFFIX, JID_USER_SUFFIX } from '../constants.js';

/** Truncate a string response to CHARACTER_LIMIT with a note */
export function truncateResponse(text: string): string {
  if (text.length <= CHARACTER_LIMIT) return text;
  const truncated = text.slice(0, CHARACTER_LIMIT);
  return truncated + `\n\n[Response truncated at ${CHARACTER_LIMIT} characters]`;
}

/** Format a successful JSON response as markdown code block */
export function formatJson(data: unknown): string {
  return truncateResponse(JSON.stringify(data, null, 2));
}

/** Format an error response */
export function formatError(error: unknown): string {
  if (error instanceof Error) {
    return `Error: ${error.message}`;
  }
  return `Error: ${String(error)}`;
}

/** Normalize a phone number to WhatsApp user JID format */
export function toUserJid(phoneOrJid: string): string {
  const cleaned = phoneOrJid.trim();
  if (cleaned.includes('@')) return cleaned;
  // Strip non-digits
  const digits = cleaned.replace(/\D/g, '');
  return `${digits}${JID_USER_SUFFIX}`;
}

/** Check if a JID is a group */
export function isGroupJid(jid: string): boolean {
  return jid.endsWith(JID_GROUP_SUFFIX);
}

/** Extract phone number from user JID */
export function jidToPhone(jid: string): string {
  return jid.replace(JID_USER_SUFFIX, '').replace(JID_GROUP_SUFFIX, '');
}

/** Convert Unix timestamp to ISO string */
export function timestampToIso(ts: number | Long | null | undefined): string {
  if (ts == null) return '';
  const num = typeof ts === 'number' ? ts : Number(ts);
  return new Date(num * 1000).toISOString();
}

/** Safely fetch a URL and return ArrayBuffer */
export async function fetchBuffer(url: string): Promise<Buffer> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url}: ${res.status} ${res.statusText}`);
  }
  const arrayBuf = await res.arrayBuffer();
  return Buffer.from(arrayBuf);
}

/** Parse base64 data URI or raw base64 string into Buffer */
export function parseBase64(input: string): Buffer {
  // Strip data URI prefix if present: data:image/png;base64,<data>
  const match = input.match(/^data:[^;]+;base64,(.+)$/);
  const base64 = match ? match[1] : input;
  return Buffer.from(base64, 'base64');
}

/** Clamp a number between min and max */
export function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

// Re-export Long type placeholder so callers don't need to import separately
export type Long = { toNumber(): number };
