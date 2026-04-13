import { WhatsAppManager, type WhatsAppStatus } from './whatsapp.js';
import { DEFAULT_ACCOUNT } from './constants.js';

/**
 * Registry of WhatsApp accounts — maps accountId → WhatsAppManager.
 *
 * Account IDs are initialized from the WHATSAPP_ACCOUNTS env var
 * (comma-separated, e.g. "default,work,personal").
 * Falls back to a single "default" account if env var is not set.
 */
class WhatsAppRegistry {
  private accounts = new Map<string, WhatsAppManager>();

  /** Initialize all configured accounts (non-blocking — connections happen in background) */
  async init(accountIds: string[]): Promise<void> {
    for (const id of accountIds) {
      if (!this.accounts.has(id)) {
        const manager = new WhatsAppManager(id);
        this.accounts.set(id, manager);
        // Fire-and-forget: QR code / reconnect logic handled inside manager
        manager.init().catch((err: unknown) => {
          process.stderr.write(`[WhatsApp registry] Init error for "${id}": ${String(err)}\n`);
        });
      }
    }
  }

  /**
   * Get the manager for a given account ID.
   * Throws with a helpful message if the account was not configured.
   */
  getManager(accountId: string = DEFAULT_ACCOUNT): WhatsAppManager {
    const manager = this.accounts.get(accountId);
    if (!manager) {
      const available = this.listAccounts().join(', ') || '(none)';
      throw new Error(
        `WhatsApp account "${accountId}" not found. ` +
          `Configured accounts: ${available}. ` +
          `Set WHATSAPP_ACCOUNTS env var to add more accounts.`
      );
    }
    return manager;
  }

  /** List all configured account IDs */
  listAccounts(): string[] {
    return Array.from(this.accounts.keys());
  }

  /** Get status snapshot for all accounts */
  getAllStatuses(): Record<string, WhatsAppStatus> {
    const result: Record<string, WhatsAppStatus> = {};
    for (const [id, manager] of this.accounts) {
      result[id] = manager.getStatus();
    }
    return result;
  }
}

/** Parse WHATSAPP_ACCOUNTS env var into a list of account IDs */
export function parseAccountsEnv(): string[] {
  const raw = process.env.WHATSAPP_ACCOUNTS ?? '';
  const ids = raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  return ids.length > 0 ? ids : [DEFAULT_ACCOUNT];
}

export const registry = new WhatsAppRegistry();
