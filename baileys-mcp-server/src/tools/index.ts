import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { registerConnectionTools } from './connection.js';
import { registerMessagingTools } from './messaging.js';
import { registerGroupTools } from './groups.js';

/** Register all WhatsApp MCP tools on the given server instance */
export function registerAllTools(server: McpServer): void {
  registerConnectionTools(server);
  registerMessagingTools(server);
  registerGroupTools(server);
}
