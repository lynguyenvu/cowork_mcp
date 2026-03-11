# Pancake MCP Server

MCP (Model Context Protocol) server kết nối Claude AI với **Pancake POS** — nền tảng quản lý bán hàng đa kênh phổ biến tại Việt Nam.

## Cấu trúc Project

```
cowork_mcp/
├── pancake-mcp-server/      # MCP server chính (Python/FastMCP)
│   ├── src/pancake_mcp/     # Source code
│   ├── tests/               # Unit tests
│   ├── docs/                # Documentation
│   ├── Dockerfile           # Docker image
│   └── docker-compose.yml   # Docker compose config
├── servers/pancake-mcp/     # Docker MCP Registry submission
│   ├── server.yaml          # Server metadata
│   └── tools.json           # Tools definition
├── docs/                    # Project docs
├── plans/                   # Development plans
└── Taskfile.yaml            # Task runner commands
```

## Tính năng chính

- **32 MCP tools** cho Pancake API
- **2 chế độ kết nối**: stdio (Claude Desktop) & HTTP (Claude.ai)
- **Modules**:
  - Shop & Payment methods
  - Đơn hàng (CRUD, tags, promotions)
  - Kho hàng (warehouses, inventory history)
  - Vận chuyển (shipment, tracking, returns)
  - Hội thoại/Inbox (Facebook, Zalo...)
  - File đính kèm (download, preview, OCR)
  - Địa lý Việt Nam (provinces, districts, communes)

## Quick Start

```bash
# Clone
git clone https://github.com/lynguyenvu/pancake-mcp-server.git
cd pancake-mcp-server

# Docker (khuyên dùng)
docker compose up -d

# Hoặc cài thủ công
pip install -e .
PANCAKE_API_KEY=your_key pancake-mcp-stdio
```

## Tech Stack

| Thành phần | Mô tả |
|------------|-------|
| Python 3.11+ | Runtime |
| FastMCP | MCP framework |
| httpx | Async HTTP client |
| uvicorn | ASGI server |
| Pillow/pytesseract | Image processing & OCR |

## Tài liệu

- [README chi tiết](./pancake-mcp-server/README.md) - Hướng dẫn cài đặt đầy đủ
- [User Guide](./pancake-mcp-server/docs/user-guide.md) - Hướng dẫn sử dụng
- [CLAUDE.md](./pancake-mcp-server/CLAUDE.md) - Context cho AI assistants

## Task Commands

```bash
task build           # Build Docker image
task test            # Test server locally
task validate-tools  # Validate tools.json
task package         # Create submission package
task submit-check    # Check submission requirements
```

## License

MIT License
