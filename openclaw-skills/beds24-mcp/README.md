# Beds24 MCP for OpenClaw

## Overview

This folder contains the OpenClaw skill integration for Beds24 MCP server.

## Components

- `docker-compose.yml` - Docker Compose stack (MCP server + Gateway)
- `Dockerfile.gateway` - Gateway image definition
- `beds24-mcp-gateway.py` - HTTP Gateway for REST → MCP translation
- `SKILL.md` - OpenClaw skill definition

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Beds24 API token

### Setup

1. Set environment variable:
```bash
export BEDS24_API_TOKEN=your_api_token_here
```

2. Start the stack:
```bash
docker compose up --build -d
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| beds24-mcp | 8761 | MCP server |
| beds24-mcp-gateway | 8767 | HTTP REST API |

### Endpoints

- `GET /health` - Health check
- `GET /tools` - List available tools
- `GET /bookings` - List bookings
- `GET /properties` - List properties
- `GET /availability` - Check availability
- More in `beds24-mcp-gateway.py`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BEDS24_API_TOKEN` | Yes | Beds24 API authentication token |
| `BEDS24_MCP_URL` | No | MCP server URL (default: http://beds24-mcp:8001) |
| `GATEWAY_PORT` | No | Gateway port (default: 8767) |

## Development

### Build and run locally

```bash
docker compose up --build
```

### Test gateway

```bash
curl http://localhost:8767/health
curl http://localhost:8767/tools
```

### Test MCP tools via gateway

```bash
# List bookings
curl -X POST http://localhost:8767/tools/beds24_list_bookings \
  -H "Content-Type: application/json" \
  -d '{"limit": 10}'
```

## Files

```
beds24-mcp/
├── docker-compose.yml       # Docker stack
├── Dockerfile.gateway      # Gateway image
├── beds24-mcp-gateway.py   # Gateway code
├── SKILL.md                # Skill definition
└── README.md               # This file
```