# Human MCP for OpenClaw

## Overview

This folder contains the OpenClaw skill integration for Human MCP server (AI + Browser Automation using Gemini and Playwright).

## Components

- `docker-compose.yml` - Docker Compose stack (MCP server + Gateway)
- `Dockerfile.gateway` - Gateway image definition
- `human-mcp-gateway.py` - HTTP Gateway for REST → MCP translation
- `SKILL.md` - OpenClaw skill definition

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Google Gemini API Key

### Setup

1. Set environment variable:
```bash
export GOOGLE_GEMINI_API_KEY=your_gemini_api_key_here
```

2. Start the stack:
```bash
docker compose up --build -d
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| human-mcp | 3100 | MCP server (npx @goonnguyen/human-mcp) |
| human-mcp-gateway | 8768 | HTTP REST API |

### Endpoints

- `GET /health` - Health check
- `GET /tools` - List available tools
- `POST /tools/{tool_name}` - Call MCP tool
- Full MCP JSON-RPC at `http://localhost:3100/mcp`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_GEMINI_API_KEY` | Yes | Google Gemini API key |
| `HUMAN_MCP_URL` | No | MCP server URL (default: http://human-mcp:3100) |
| `GATEWAY_PORT` | No | Gateway port (default: 8768) |

## Development

### Build and run locally

```bash
docker compose up --build
```

### Test gateway

```bash
curl http://localhost:8768/health
curl http://localhost:8768/tools
```

### Test MCP tools via gateway

```bash
# List tools
curl -X POST http://localhost:8768/tools/list_tools \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Features

- **AI**: Google Gemini integration for AI capabilities
- **Browser Automation**: Playwright for web automation
- **Multi-API Support**: Can use MiniMax, ElevenLabs, Zhipu, RMBG APIs

## Files

```
human-mcp/
├── docker-compose.yml       # Docker stack
├── Dockerfile.gateway      # Gateway image
├── human-mcp-gateway.py    # Gateway code
├── SKILL.md                # Skill definition
└── README.md               # This file
```