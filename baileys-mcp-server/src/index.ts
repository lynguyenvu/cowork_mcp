/**
 * WhatsApp MCP Server
 *
 * Supports two transport modes:
 * - stdio (default): for Claude Desktop integration. QR code printed to stderr.
 * - streamable-http: for Docker/VPS deployment (set TRANSPORT=streamable-http).
 *   Exposes /mcp endpoint for MCP protocol, /qr for QR code, /health for status.
 *
 * Auth credentials saved to AUTH_DIR (default: ./auth_info/) for auto-reconnect.
 */

import http from 'http';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { registry, parseAccountsEnv } from './whatsapp-registry.js';
import { registerAllTools } from './tools/index.js';

const TRANSPORT = process.env.TRANSPORT ?? 'stdio';
const PORT = parseInt(process.env.PORT ?? '8769', 10);

async function main(): Promise<void> {
  // ── 1. Init all configured WhatsApp accounts (non-blocking) ──────────────
  const accountIds = parseAccountsEnv();
  process.stderr.write(`[WhatsApp MCP] Initializing accounts: ${accountIds.join(', ')}\n`);
  registry.init(accountIds).catch((err: unknown) => {
    process.stderr.write(`[WhatsApp MCP] Registry init error: ${String(err)}\n`);
  });

  // ── 2. Create and configure MCP server ────────────────────────────────────
  // For stdio: single server instance. For HTTP: new server per request (SDK stateless requirement).
  const server = new McpServer(
    { name: 'whatsapp-mcp', version: '1.0.0' },
    { capabilities: { tools: {} } }
  );
  registerAllTools(server);

  // ── 3. Connect transport ──────────────────────────────────────────────────
  if (TRANSPORT === 'streamable-http') {
    await startHttpServer();
  } else {
    await startStdioServer(server);
  }

  // ── 5. Graceful shutdown ──────────────────────────────────────────────────
  const shutdown = (signal: string): void => {
    process.stderr.write(`\n[WhatsApp MCP] Received ${signal}, shutting down...\n`);
    process.exit(0);
  };
  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
}

async function startStdioServer(server: McpServer): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write('[WhatsApp MCP] Ready on stdio transport\n');
}

async function startHttpServer(): Promise<void> {
  // SDK v1.10+ stateless mode: BOTH McpServer AND transport must be fresh per request.
  // A McpServer can only be connected to one transport at a time.

  const httpServer = http.createServer(async (req, res) => {
    const url = req.url ?? '/';

    // ── /health — all accounts status ───────────────────────────────────────
    if (url === '/health') {
      const accounts = registry.getAllStatuses();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', accounts }));
      return;
    }

    // ── /qr?account={id} — QR code for initial WhatsApp auth ────────────────
    if (url === '/qr' || url.startsWith('/qr?')) {
      const account = new URL(url, 'http://localhost').searchParams.get('account') ?? 'default';
      try {
        const { status, qrCode } = registry.getManager(account).getStatus();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ account, status, qrCode }));
      } catch (err) {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: String(err) }));
      }
      return;
    }

    // ── /mcp — MCP Streamable HTTP protocol ─────────────────────────────────
    if (url === '/mcp' || url.startsWith('/mcp?') || url.startsWith('/mcp/')) {
      // Create fresh McpServer + transport per request (SDK v1.10+ stateless requirement)
      const reqServer = new McpServer(
        { name: 'whatsapp-mcp', version: '1.0.0' },
        { capabilities: { tools: {} } }
      );
      registerAllTools(reqServer);
      const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
      await reqServer.connect(transport);

      try {
        let parsedBody: unknown;
        if (req.method === 'POST') {
          parsedBody = await readJsonBody(req);
        }
        await transport.handleRequest(req, res, parsedBody);
      } catch (err) {
        process.stderr.write(`[WhatsApp MCP] Request error: ${String(err)}\n`);
        if (!res.headersSent) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Internal server error' }));
        }
      }
      return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
  });

  httpServer.listen(PORT, '0.0.0.0', () => {
    process.stderr.write(`[WhatsApp MCP] Ready on http://0.0.0.0:${PORT}/mcp\n`);
    process.stderr.write(`[WhatsApp MCP] QR code:  GET http://0.0.0.0:${PORT}/qr\n`);
    process.stderr.write(`[WhatsApp MCP] Health:   GET http://0.0.0.0:${PORT}/health\n`);
  });
}

/** Read and parse JSON body from an IncomingMessage */
function readJsonBody(req: http.IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on('data', (chunk: Buffer) => chunks.push(chunk));
    req.on('end', () => {
      try {
        const raw = Buffer.concat(chunks).toString('utf8');
        resolve(raw ? JSON.parse(raw) : undefined);
      } catch (err) {
        reject(err);
      }
    });
    req.on('error', reject);
  });
}

main().catch((err: unknown) => {
  process.stderr.write(`[WhatsApp MCP] Fatal error: ${String(err)}\n`);
  process.exit(1);
});
