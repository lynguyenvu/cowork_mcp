import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { registry } from '../whatsapp-registry.js';
import {
  formatError,
  formatJson,
  toUserJid,
  isGroupJid,
  timestampToIso,
  truncateResponse,
} from '../utils/index.js';

/** Shared account param added to every group tool */
const accountParam = z
  .string()
  .optional()
  .default('default')
  .describe('WhatsApp account ID (default: "default"). Use whatsapp_list_accounts to see all.');

export function registerGroupTools(server: McpServer): void {
  // ── whatsapp_list_groups ─────────────────────────────────────────────────
  server.tool(
    'whatsapp_list_groups',
    `List all WhatsApp groups the connected account is a member of.

Fetches group metadata for all joined groups. Results include group JID, name, participant count, and last activity.
Response is truncated at CHARACTER_LIMIT characters if there are many groups.

Parameters:
- account: WhatsApp account ID

Returns: Array of group objects with jid, name, participantCount, creation date, and description.`,
    { account: accountParam },
    { readOnlyHint: true, openWorldHint: true },
    async ({ account }) => {
      try {
        const manager = registry.getManager(account);
        const sock = manager.getSock();
        const groups = await sock.groupFetchAllParticipating();
        const list = Object.values(groups).map((g) => ({
          jid: g.id,
          name: g.subject,
          participantCount: g.participants?.length ?? 0,
          description: g.desc ?? null,
          owner: g.owner ?? null,
          createdAt: g.creation ? timestampToIso(g.creation) : null,
          isCommunity: g.isCommunity ?? false,
          isAnnouncement: g.announce ?? false,
        }));

        manager.getStore().upsertChats(list.map((g) => ({ id: g.jid, name: g.name })));

        return {
          content: [
            {
              type: 'text' as const,
              text: truncateResponse(formatJson({ account, total: list.length, groups: list })),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_get_group_info ──────────────────────────────────────────────
  server.tool(
    'whatsapp_get_group_info',
    `Get detailed metadata for a specific WhatsApp group.

Returns full group info including all participants with their roles (admin/member), group description, and settings.

Parameters:
- jid: Group JID (e.g., '1234567890-123456@g.us')
- account: WhatsApp account ID

Returns: Full group metadata object.`,
    {
      jid: z.string().min(1).describe("Group JID (must end with '@g.us')"),
      account: accountParam,
    },
    { readOnlyHint: true, openWorldHint: true },
    async ({ jid, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        if (!isGroupJid(jid)) throw new Error(`Invalid group JID: ${jid}. Must end with @g.us`);
        const meta = await sock.groupMetadata(jid);
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                jid: meta.id,
                name: meta.subject,
                description: meta.desc ?? null,
                owner: meta.owner ?? null,
                createdAt: meta.creation ? timestampToIso(meta.creation) : null,
                participantCount: meta.participants?.length ?? 0,
                participants: meta.participants?.map((p) => ({
                  jid: p.id,
                  isAdmin: p.admin === 'admin' || p.admin === 'superadmin',
                  isSuperAdmin: p.admin === 'superadmin',
                })),
                isAnnouncement: meta.announce ?? false,
                isLocked: meta.restrict ?? false,
                isCommunity: meta.isCommunity ?? false,
                linkedParent: meta.linkedParent ?? null,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_create_group ────────────────────────────────────────────────
  server.tool(
    'whatsapp_create_group',
    `Create a new WhatsApp group.

Creates a group with the specified name and initial participants.
The authenticated account is automatically set as the group admin.

Parameters:
- name: Group name (subject)
- participants: List of participant phone numbers or JIDs to add initially (at least 1)
- account: WhatsApp account ID

Returns: Created group JID and metadata.`,
    {
      name: z.string().min(1).max(100).describe('Group name/subject'),
      participants: z.array(z.string().min(1)).min(1).describe('Participant phone numbers or JIDs'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ name, participants, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        const participantJids = participants.map(toUserJid);
        const result = await sock.groupCreate(name, participantJids);
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                success: true,
                jid: result.id,
                name: result.subject,
                participantCount: result.participants?.length ?? 0,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_add_participants ────────────────────────────────────────────
  server.tool(
    'whatsapp_add_participants',
    `Add one or more participants to a WhatsApp group.

The authenticated account must be a group admin to perform this action.

Parameters:
- jid: Group JID (must end with '@g.us')
- participants: List of phone numbers or JIDs to add
- account: WhatsApp account ID

Returns: Result per participant (added/failed/already member).`,
    {
      jid: z.string().min(1).describe("Group JID (must end with '@g.us')"),
      participants: z.array(z.string().min(1)).min(1).describe('Phone numbers or JIDs to add'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ jid, participants, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        if (!isGroupJid(jid)) throw new Error(`Invalid group JID: ${jid}`);
        const result = await sock.groupParticipantsUpdate(jid, participants.map(toUserJid), 'add');
        return {
          content: [{ type: 'text' as const, text: formatJson({ success: true, results: result }) }],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_remove_participants ─────────────────────────────────────────
  server.tool(
    'whatsapp_remove_participants',
    `Remove one or more participants from a WhatsApp group.

The authenticated account must be a group admin to perform this action.

Parameters:
- jid: Group JID (must end with '@g.us')
- participants: List of phone numbers or JIDs to remove
- account: WhatsApp account ID

Returns: Result per participant.`,
    {
      jid: z.string().min(1).describe("Group JID (must end with '@g.us')"),
      participants: z.array(z.string().min(1)).min(1).describe('Phone numbers or JIDs to remove'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
    async ({ jid, participants, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        if (!isGroupJid(jid)) throw new Error(`Invalid group JID: ${jid}`);
        const result = await sock.groupParticipantsUpdate(jid, participants.map(toUserJid), 'remove');
        return {
          content: [{ type: 'text' as const, text: formatJson({ success: true, results: result }) }],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_update_group_subject ────────────────────────────────────────
  server.tool(
    'whatsapp_update_group_subject',
    `Update the name (subject) of a WhatsApp group.

The authenticated account must be a group admin.

Parameters:
- jid: Group JID (must end with '@g.us')
- subject: New group name (1-100 characters)
- account: WhatsApp account ID

Returns: Confirmation with updated name.`,
    {
      jid: z.string().min(1).describe("Group JID (must end with '@g.us')"),
      subject: z.string().min(1).max(100).describe('New group name'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    async ({ jid, subject, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        if (!isGroupJid(jid)) throw new Error(`Invalid group JID: ${jid}`);
        await sock.groupUpdateSubject(jid, subject);
        return {
          content: [{ type: 'text' as const, text: formatJson({ success: true, jid, newSubject: subject }) }],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_update_group_description ────────────────────────────────────
  server.tool(
    'whatsapp_update_group_description',
    `Update the description of a WhatsApp group. The account must be a group admin.
Pass an empty string to clear the description.

Parameters:
- jid: Group JID (must end with '@g.us')
- description: New group description (empty string to clear)
- account: WhatsApp account ID

Returns: Confirmation.`,
    {
      jid: z.string().min(1).describe("Group JID (must end with '@g.us')"),
      description: z.string().describe('New description (empty to clear)'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    async ({ jid, description, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        if (!isGroupJid(jid)) throw new Error(`Invalid group JID: ${jid}`);
        await sock.groupUpdateDescription(jid, description || undefined);
        return {
          content: [{ type: 'text' as const, text: formatJson({ success: true, jid, descriptionUpdated: true }) }],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_get_invite_link ──────────────────────────────────────────────
  server.tool(
    'whatsapp_get_invite_link',
    `Get the invite link for a WhatsApp group.

The authenticated account must be a group admin or have permission to view the invite link.

Parameters:
- jid: Group JID (must end with '@g.us')
- reset: Reset (revoke) the existing invite link and generate a new one (default: false)
- account: WhatsApp account ID

Returns: Invite link URL.`,
    {
      jid: z.string().min(1).describe("Group JID (must end with '@g.us')"),
      reset: z.boolean().optional().default(false).describe('Revoke current link and generate new one'),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    async ({ jid, reset, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        if (!isGroupJid(jid)) throw new Error(`Invalid group JID: ${jid}`);
        const code = reset
          ? ((await sock.groupRevokeInvite(jid)) ?? '')
          : ((await sock.groupInviteCode(jid)) ?? '');
        return {
          content: [
            {
              type: 'text' as const,
              text: formatJson({
                jid,
                inviteLink: `https://chat.whatsapp.com/${code}`,
                inviteCode: code,
                reset,
              }),
            },
          ],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );

  // ── whatsapp_leave_group ─────────────────────────────────────────────────
  server.tool(
    'whatsapp_leave_group',
    `Leave a WhatsApp group. The action cannot be undone without a new invite.

Parameters:
- jid: Group JID (must end with '@g.us')
- account: WhatsApp account ID

Returns: Confirmation of leaving the group.`,
    {
      jid: z.string().min(1).describe("Group JID (must end with '@g.us')"),
      account: accountParam,
    },
    { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
    async ({ jid, account }) => {
      try {
        const sock = registry.getManager(account).getSock();
        if (!isGroupJid(jid)) throw new Error(`Invalid group JID: ${jid}`);
        await sock.groupLeave(jid);
        return {
          content: [{ type: 'text' as const, text: formatJson({ success: true, jid, action: 'left_group' }) }],
        };
      } catch (err) {
        return { content: [{ type: 'text' as const, text: formatError(err) }], isError: true };
      }
    }
  );
}
