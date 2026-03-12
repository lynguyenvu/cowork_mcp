# Cowork MCP Servers

MCP (Model Context Protocol) servers kết nối Claude AI với các nền tảng quản lý kinh doanh.

## MCP Servers

### 1. Pancake MCP Server
**Pancake POS** — Nền tảng quản lý bán hàng đa kênh phổ biến tại Việt Nam.

- **32 MCP tools** cho Pancake API
- **Modules**: Shop, Đơn hàng, Kho hàng, Vận chuyển, Hội thoại, File đính kèm, Địa lý VN
- [Chi tiết](./pancake-mcp-server/README.md)

### 2. Beds24 MCP Server
**Beds24** — Hệ thống quản lý khách sạn và đặt phòng (Property Management System).

- **12 MCP tools** cho Beds24 API v2
- **Modules**: Booking, Property, Inventory & Pricing
- [Chi tiết](./beds24-mcp-server/README.md)

## Cấu trúc Project

```
cowork_mcp/
├── pancake-mcp-server/      # Pancake POS MCP server
├── beds24-mcp-server/       # Beds24 PMS MCP server
├── servers/                 # MCP Registry submissions
│   ├── pancake-mcp/
│   └── beds24-mcp/
├── docs/                    # Project docs
└── plans/                   # Development plans
```

## Quick Start

### Pancake MCP Server

```bash
cd pancake-mcp-server
docker compose up -d
# hoặc
pip install -e .
PANCAKE_API_KEY=your_key pancake-mcp-stdio
```

### Beds24 MCP Server

```bash
cd beds24-mcp-server
docker compose up -d
# hoặc
pip install -r requirements.txt
BEDS24_API_TOKEN=your_token python server.py --transport streamable-http --port 8001
```

## Kết nối với Open WebUI

### Pancake MCP

1. Copy config: `cp pancake-mcp-server/config-openwebui.json /path/to/open-webui/mcp/config.json`
2. Thêm API key vào config
3. Restart Open WebUI

### Beds24 MCP

1. Copy config: `cp beds24-mcp-server/config-openwebui.json /path/to/open-webui/mcp/config.json`
2. Thêm API token vào config
3. Restart Open WebUI

Xem chi tiết: [SETUP_OPENWEBUI.md](./beds24-mcp-server/SETUP_OPENWEBUI.md)

## Tech Stack

| Thành phần | Mô tả |
|------------|-------|
| Python 3.11+ | Runtime |
| FastMCP | MCP framework |
| httpx | Async HTTP client |
| uvicorn | ASGI server |
| Pydantic | Data validation |

## License

MIT License
