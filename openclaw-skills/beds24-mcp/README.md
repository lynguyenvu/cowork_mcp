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
- Beds24 refresh token (recommended) or API token

### Setup

1. Set environment variable:
```bash
export BEDS24_REFRESH_TOKEN=your_refresh_token_here
```

2. Start the stack:
```bash
docker compose up --build -d
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| beds24-mcp | 8001 | MCP server |
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
| `BEDS24_REFRESH_TOKEN` | Yes* | Beds24 refresh token (auto-refreshes access token) |
| `BEDS24_API_TOKEN` | Alt | Alternative: Long-life API token (read-only) |
| `BEDS24_MCP_URL` | No | MCP server URL (default: http://beds24-mcp:8001) |
| `GATEWAY_PORT` | No | Gateway port (default: 8767) |

*Use refresh token for full read/write access. API token provides read-only access.

## API Notes

- **List bookings filters**: Use `arrival` and `departure` params (YYYY-MM-DD format)
- **Get booking**: Uses query param `?id=xxx`, not path `/bookings/xxx`
- **Pagination**: API returns max 100 per request; auto-pagination enabled up to 1000 records
- **Response format**: `{success: true, data: [...], count: N}`
- **Include params**: `includeInvoiceItems`, `includeInfoItems`, `includeBookingGroup` (default: true)

## Development

### Build and run locally

```bash
docker compose up --build
```

### Test health

```bash
curl http://localhost:8001/health
# Response: {"status": "ok", "server": "beds24-mcp"}
```

### Test gateway

```bash
curl http://localhost:8767/health
curl http://localhost:8767/tools
```

### Test MCP tools via gateway

```bash
# List bookings with arrival filter
curl -X POST http://localhost:8767/tools/beds24_list_bookings \
  -H "Content-Type: application/json" \
  -d '{"arrival": "2026-03-18", "limit": 5}'

# List bookings with departure filter
curl -X POST http://localhost:8767/tools/beds24_list_bookings \
  -H "Content-Type: application/json" \
  -d '{"departure": "2026-03-20", "limit": 5}'

# Get booking by ID
curl -X POST http://localhost:8767/tools/beds24_get_booking \
  -H "Content-Type: application/json" \
  -d '{"booking_id": "83868227"}'
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