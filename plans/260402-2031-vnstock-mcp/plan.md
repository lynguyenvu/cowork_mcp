---
title: "VNStock MCP Server"
description: "Build MCP server for Vietnamese stock market data using vnstock library"
status: pending
priority: P2
effort: 3h
branch: master
tags: [mcp, vnstock, vietnam-stock, python, fastmcp]
created: 2026-04-02
---

# VNStock MCP Server - Implementation Plan

## Overview

Build an MCP server wrapping the [vnstock](https://github.com/thinh-vu/vnstock) Python library, providing Vietnamese stock market data to AI assistants via Model Context Protocol.

**Reference implementation**: [mrgoonie/vnstock-agent](https://github.com/mrgoonie/vnstock-agent) — existing open-source MCP server with 21 tools. Our implementation adapts this to the cowork_mcp project conventions (single `server.py`, Docker-first, streamable-http transport).

## Data Flow

```
Client (Claude/OpenWebUI) → MCP Protocol (streamable-http :8002)
  → FastMCP server.py → vnstock library → VCI/KBS/MSN data sources
  → DataFrame → JSON → MCP response
```

## Tools (21 tools, 6 categories)

### Quote (3 tools)
| Tool | Description | Key Params |
|------|-------------|------------|
| `stock_history` | Historical OHLCV | symbol, start, end, interval, source |
| `stock_intraday` | Today's tick data | symbol, page_size, source |
| `stock_price_depth` | Order book bid/ask | symbol, source |

### Company (5 tools)
| Tool | Description |
|------|-------------|
| `company_overview` | Market cap, industry, description |
| `company_shareholders` | Major shareholders |
| `company_officers` | Management team |
| `company_news` | Latest news |
| `company_events` | Dividends, AGM, earnings |

### Financials (4 tools)
| Tool | Description | Key Params |
|------|-------------|------------|
| `financial_balance_sheet` | Balance sheet | symbol, period (quarter/annual) |
| `financial_income_statement` | P&L statement | symbol, period |
| `financial_cash_flow` | Cash flow statement | symbol, period |
| `financial_ratio` | P/E, P/B, ROE, ROA | symbol, period |

### Listing (4 tools)
| Tool | Description |
|------|-------------|
| `listing_all_symbols` | All HOSE/HNX/UPCOM symbols |
| `listing_symbols_by_group` | VN30, HNX30, etc. |
| `listing_symbols_by_exchange` | Grouped by exchange |
| `listing_industries` | ICB classification |

### Trading (1 tool)
| Tool | Description |
|------|-------------|
| `trading_price_board` | Real-time price board (multi-symbol) |

### Global Markets (4 tools)
| Tool | Description |
|------|-------------|
| `fx_history` | Forex pairs (EURUSD, USDJPY) |
| `crypto_history` | Crypto (BTC, ETH, SOL) |
| `world_index_history` | DJI, NASDAQ, S&P 500 |
| `fund_listing` | Vietnamese mutual funds |

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Runtime | Python 3.12 | Match existing servers |
| MCP Framework | FastMCP >= 2.0 | Project standard |
| Data Library | vnstock >= 3.5.0 | Core dependency |
| Transport | streamable-http | Project convention (beds24 pattern) |
| Container | Docker + Alpine | Lightweight, match existing |
| Port | 8002 | Next available (beds24=8001) |

## File Structure

```
/cowork_mcp/servers/vnstock-mcp/
├── server.py              # MCP server + tools + core logic (single file)
├── requirements.txt       # Python deps
├── Dockerfile             # Alpine-based container
├── docker-compose.yml     # Service definition
├── config-openwebui.json  # Open WebUI integration config
└── README.md              # Setup & usage docs
```

**Design decision**: Single `server.py` file (~200 lines) combining tool definitions and core logic. The reference repo splits into 4 files (server/core/config/cli), but our servers follow a simpler single-file pattern. We skip CLI since we only need MCP transport.

## Implementation Phases

### Phase 1: Core Server (1.5h) `[pending]`

**Files**: `server.py`, `requirements.txt`

**Steps**:
1. Create `requirements.txt` with: vnstock>=3.5.0, fastmcp>=2.0.0, pandas>=1.5.0, uvicorn>=0.20.0
2. Implement `server.py`:
   - Config section: env vars (VNSTOCK_API_KEY, VNSTOCK_SOURCE, port/host)
   - API key registration with stdout suppression (vnstock prints noise)
   - Helper: `_df_to_records()` — DataFrame→dict conversion handling NaN, MultiIndex, timestamps
   - Helper: `_default_dates()` — 30-day default window
   - Helper: `_safe_call()` — try/except wrapper returning error dict
   - 21 MCP tool functions using FastMCP decorators
   - Transport entry point (streamable-http default, stdio fallback)
3. Key adaptations from reference:
   - Merge `core.py` logic inline into tool functions
   - Use `Vnstock` class (not separate Quote/Finance imports) for unified API
   - Suppress vnstock/vnai stdout pollution in all calls

**Failure modes**:
- vnstock API key invalid → tools return `{"error": "..."}`, server stays up
- vnstock lib version mismatch → pin in requirements.txt
- DataFrame MultiIndex columns → flatten with `_df_to_records()` (reference has this solved)

**Success criteria**: Server starts, responds to tool list request, returns data for `stock_history("VNM")`

### Phase 2: Docker & Deployment (0.5h) `[pending]`

**Files**: `Dockerfile`, `docker-compose.yml`, `config-openwebui.json`

**Steps**:
1. `Dockerfile`:
   - Base: python:3.12-alpine
   - Install gcc/musl-dev for pandas build, cleanup after pip install
   - Default env: VNSTOCK_MCP_TRANSPORT=streamable-http, port 8002
   - CMD: python server.py
2. `docker-compose.yml`:
   - Service `vnstock-mcp`, port 8002:8002
   - Environment from .env (VNSTOCK_API_KEY)
   - Healthcheck: curl localhost:8002/health (if FastMCP exposes it)
   - restart: unless-stopped
3. `config-openwebui.json`: MCP client config pointing to http://vnstock-mcp:8002

**Failure modes**:
- pandas/numpy build fails on Alpine → add build deps, remove after install
- Port conflict → configurable via env var

### Phase 3: Documentation & Integration (0.5h) `[pending]`

**Files**: `README.md`, update root `/cowork_mcp/README.md`

**Steps**:
1. Write `servers/vnstock-mcp/README.md`: setup, env vars, tool list, examples
2. Update root README.md to add VNStock MCP as server #3
3. Test docker compose up end-to-end

### Phase 4: Testing (0.5h) `[pending]`

**Files**: `test_server.py`

**Steps**:
1. Unit test `_df_to_records()` with edge cases (empty df, MultiIndex, NaN, tuple keys)
2. Integration test: start server, call stock_history tool
3. Verify all 21 tools registered and callable

**Test matrix**:
| Test | Type | What |
|------|------|------|
| df_to_records_empty | Unit | Empty DataFrame → [] |
| df_to_records_multiindex | Unit | MultiIndex columns flattened |
| df_to_records_nan | Unit | NaN → None |
| server_starts | Integration | Server binds to port |
| tool_registration | Integration | 21 tools in tool list |
| stock_history_call | Integration | Returns OHLCV data |
| invalid_symbol | Integration | Returns error dict, no crash |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| vnstock API rate limiting | Medium | Medium | Add retry logic in _safe_call |
| vnstock breaking changes | Low | High | Pin version, test on upgrade |
| API key required for all calls | High | Low | Clear error msg if missing |
| Large DataFrame responses | Medium | Medium | Truncate to last N records in tools |
| pandas build on Alpine | Low | Medium | Multi-stage Docker build if needed |

## Rollback

- Server is isolated in its own directory, no shared files with other servers
- Docker container can be stopped independently
- Only shared file change: root README.md (easily revertible)

## Dependencies

- Phase 2 depends on Phase 1
- Phase 3 depends on Phase 2
- Phase 4 can run parallel with Phase 3

## Unresolved Questions

1. **VNSTOCK_API_KEY**: Is there a shared key for the project, or does each user need their own? (free tier at vnstocks.com/login)
2. **Data source default**: Reference uses VCI, beds24 project has no opinion. Should we default to VCI or KBS?
3. **Response size**: Should we cap large responses (e.g., listing_all_symbols returns 1500+ records)? Could add optional `limit` param.
