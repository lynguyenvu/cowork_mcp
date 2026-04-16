/**
 * Human MCP HTTP Gateway
 *
 * Wraps the stdio-based @goonnguyen/human-mcp package
 * and exposes it via HTTP transport for OpenClaw integration.
 */

const { spawn } = require('child_process');
const http = require('http');
const { URL } = require('url');

const PORT = process.env.PORT || 3100;
const MCP_SERVER_CMD = 'human-mcp';
const MCP_SERVER_ARGS = [];

// Store active MCP processes
const mcpProcesses = new Map();

// Parse JSON body from request
async function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        resolve(JSON.parse(body));
      } catch (e) {
        resolve({});
      }
    });
    req.on('error', reject);
  });
}

// Create MCP stdio process
function createMCPProcess() {
  const env = { ...process.env };

  console.log(`[MCP] Starting: ${MCP_SERVER_CMD} ${MCP_SERVER_ARGS.join(' ')}`);

  const proc = spawn(MCP_SERVER_CMD, MCP_SERVER_ARGS, {
    env,
    stdio: ['pipe', 'pipe', 'pipe']
  });

  proc.stderr.on('data', (data) => {
    console.error(`[MCP stderr] ${data.toString().trim()}`);
  });

  proc.on('error', (err) => {
    console.error('[MCP process error]', err);
  });

  proc.on('exit', (code) => {
    console.log(`[MCP process exited with code ${code}]`);
    mcpProcess = null; // Reset so it can be recreated
  });

  return proc;
}

// Send request to MCP process and get response
async function callMCP(proc, request) {
  // Check if this is a notification (no id)
  const isNotification = request.id === undefined || request.id === null;

  if (isNotification) {
    // Notifications are fire-and-forget, no response expected
    // Don't forward to MCP process - just acknowledge immediately
    console.log(`[MCP Notification] ${request.method} (no id) - acknowledged`);
    return { jsonrpc: '2.0', result: null };
  }

  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('MCP request timeout'));
    }, 60000); // 1 minute timeout (GoClaw usually has 30s)

    let responseBuffer = '';
    let resolved = false;

    const onData = (data) => {
      responseBuffer += data.toString();
      const lines = responseBuffer.split('\n');
      responseBuffer = lines.pop(); // Keep incomplete line in buffer

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const response = JSON.parse(line);
          if (response.id === request.id) {
            if (!resolved) {
              resolved = true;
              clearTimeout(timeout);
              proc.stdout.off('data', onData);
              resolve(response);
            }
            return;
          }
        } catch (e) {
          // Not valid JSON, continue
        }
      }
    };

    proc.stdout.on('data', onData);
    const requestLine = JSON.stringify(request) + '\n';
    console.log(`[MCP Request] ${request.method} (id: ${request.id})`);
    proc.stdin.write(requestLine);
  });
}

// Initialize MCP process
let mcpProcess = null;

async function initMCP() {
  if (!mcpProcess) {
    console.log('[Init] Starting MCP process...');
    mcpProcess = createMCPProcess();
    // Wait longer for process to be ready (npx install + package startup)
    await new Promise(r => setTimeout(r, 5000));
    console.log('[Init] MCP process ready');
  }
  return mcpProcess;
}

// Create HTTP server
const server = http.createServer(async (req, res) => {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  const url = new URL(req.url, `http://localhost:${PORT}`);

  // Health endpoint
  if (url.pathname === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      transport: 'stdio-gateway',
      server: 'human-mcp-wrapper'
    }));
    return;
  }

  // MCP endpoint
  if (url.pathname === '/mcp') {
    let body = null;
    try {
      body = await parseBody(req);

      if (!body.method) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Missing method' }));
        return;
      }

      console.log(`[HTTP] ${body.method} request received`);

      const proc = await initMCP();
      const response = await callMCP(proc, body);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(response));
    } catch (err) {
      console.error('MCP error:', err);
      // Reset process on error so it can be recreated
      if (mcpProcess) {
        try {
          mcpProcess.kill();
        } catch (e) {}
        mcpProcess = null;
      }
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        error: err.message,
        jsonrpc: '2.0',
        id: body?.id || null
      }));
    }
    return;
  }

  // 404
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
});

// Start server
server.listen(PORT, () => {
  console.log(`Human MCP HTTP Gateway listening on port ${PORT}`);
  console.log(`Health: http://localhost:${PORT}/health`);
  console.log(`MCP: http://localhost:${PORT}/mcp`);
});

// Cleanup on exit
process.on('SIGTERM', () => {
  console.log('Shutting down...');
  if (mcpProcess) {
    mcpProcess.kill();
  }
  server.close();
});

process.on('SIGINT', () => {
  console.log('Shutting down...');
  if (mcpProcess) {
    mcpProcess.kill();
  }
  server.close();
});
