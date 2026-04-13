import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { registry } from '../whatsapp-registry.js';
import { formatError } from '../utils/index.js';

/** Shared account param added to every connection tool */
const accountParam = z
  .string()
  .optional()
  .default('default')
  .describe('WhatsApp account ID (default: "default"). Use whatsapp_list_accounts to see all.');

export function registerConnectionTools(server: McpServer): void {
  // ── whatsapp_list_accounts ───────────────────────────────────────────────
  server.tool(
    'whatsapp_list_accounts',
    `List all configured WhatsApp accounts and their connection statuses.

Each account corresponds to a separate WhatsApp number. Accounts are configured via
the WHATSAPP_ACCOUNTS environment variable (comma-separated IDs, e.g. "default,work,sales").

Returns: Array of account objects with accountId, status, phoneNumber, and isLoggedIn.`,
    {},
    { readOnlyHint: true, openWorldHint: false },
    async () => {
      try {
        const statuses = registry.getAllStatuses();
        return {
          content: [
            {
              type: 'text' as const,
              text: JSON.stringify(
                {
                  accounts: Object.values(statuses).map((s) => ({
                    accountId: s.accountId,
                    status: s.status,
                    phoneNumber: s.phoneNumber,
                    isLoggedIn: s.isLoggedIn,
                  })),
                },
                null,
                2
              ),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_get_status ──────────────────────────────────────────────────
  server.tool(
    'whatsapp_get_status',
    `Get WhatsApp connection status, QR code, and phone number for a specific account.

Returns current connection state: 'disconnected', 'connecting', 'qr_pending', or 'connected'.
When status is 'qr_pending', a QR code is available — tell the user to scan it from
the terminal or fetch it from GET /qr?account={accountId} (HTTP transport).

Returns: JSON with accountId, status, qrCode (raw string or null), phoneNumber, isLoggedIn.`,
    { account: accountParam },
    { readOnlyHint: true, openWorldHint: false },
    async ({ account }) => {
      try {
        const status = registry.getManager(account).getStatus();
        return {
          content: [
            {
              type: 'text' as const,
              text: JSON.stringify(
                {
                  accountId: status.accountId,
                  status: status.status,
                  isLoggedIn: status.isLoggedIn,
                  phoneNumber: status.phoneNumber,
                  qrCode: status.qrCode ?? null,
                  note: status.qrCode
                    ? 'QR also shown in server terminal. Scan: WhatsApp → Linked Devices → Link a Device.'
                    : undefined,
                },
                null,
                2
              ),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_logout ──────────────────────────────────────────────────────
  server.tool(
    'whatsapp_logout',
    `Logout from WhatsApp and clear saved session credentials for a specific account.

Disconnects the WebSocket, removes auth files, and clears the in-memory message store.
A new QR scan will be required to reconnect this account.

WARNING: Destructive — the saved session is permanently deleted.

Returns: Confirmation message.`,
    { account: accountParam },
    { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false },
    async ({ account }) => {
      try {
        await registry.getManager(account).logout();
        return {
          content: [
            {
              type: 'text' as const,
              text: `Account "${account}" logged out. Auth credentials cleared. Scan QR to reconnect.`,
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );
}
