# Pancake MCP + OpenClaw Integration

Tích hợp Pancake MCP với OpenClaw để quản lý bán hàng qua AI assistant.

## Kiến trúc

```
┌─────────────┐      HTTP API      ┌─────────────────────┐      MCP      ┌─────────────────┐
│   OpenClaw  │ ─────────────────> │  Pancake MCP Gateway │ ────────────> │  Pancake MCP    │
│  (AI Agent) │   localhost:8766   │    (HTTP Wrapper)    │  localhost:8765  │  (MCP Server)   │
└─────────────┘                    └─────────────────────┘               └─────────────────┘
                                                                              │
                                                                              v
                                                                       ┌──────────────┐
                                                                       │  Pancake API │
                                                                       └──────────────┘
```

## Các Services

| Service | Port | Mô tả |
|---------|------|-------|
| Pancake MCP | 8765 | MCP server gốc |
| Pancake MCP Gateway | 8766 | HTTP API wrapper cho OpenClaw |
| Pancake MCP (Docker) | 8000 | Instance cũ vẫn chạy |

## Quick Start

### 1. Khởi động Services

```bash
cd /cowork_mcp/openclaw-skills/pancake-mcp
docker compose up -d
```

### 2. Kiểm tra Health

```bash
# Kiểm tra Gateway
curl http://localhost:8766/health

# Kiểm tra Pancake MCP
curl http://localhost:8765/health
```

### 3. Test API

```bash
# List tools
curl http://localhost:8766/tools

# Get shops
curl http://localhost:8766/shops

# Search orders
curl "http://localhost:8766/orders?status=confirmed&limit=10"

# Get order details
curl http://localhost:8766/orders/123456
```

## API Endpoints

### Health & Info
- `GET /health` - Health check
- `GET /` - API info
- `GET /tools` - List available tools

### Shop Management
- `GET /shops` - Get all shops
- `GET /provinces` - Get provinces
- `GET /districts` - Get districts
- `GET /communes` - Get communes

### Order Management
- `GET /orders` - Search orders (query: status, start_date, end_date, limit)
- `GET /orders/{order_id}` - Get order details
- `POST /tools/create_order` - Create order
- `POST /tools/update_order` - Update order

### Conversation Management
- `GET /conversations` - List conversations
- `POST /conversations/{id}/messages` - Send message

### Tool Calls
- `POST /tools/{tool_name}` - Call any MCP tool

## Cấu hình OpenClaw

### 1. Thêm MCP Server (khi OpenClaw hỗ trợ MCP)

Trong `~/.openclaw/openclaw.json`:

```json
{
  "mcpServers": {
    "pancake-mcp": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "pancake-mcp-server:latest"],
      "env": {
        "PANCAKE_API_KEY": "your_api_key"
      }
    }
  }
}
```

### 2. Sử dụng HTTP Tools (hiện tại)

OpenClaw có thể gọi HTTP endpoints trực tiếp:

```
Gọi API http://localhost:8766/shops để lấy danh sách shops
```

## Các File

```
openclaw-skills/pancake-mcp/
├── SKILL.md                    # OpenClaw skill documentation
├── pancake-mcp-gateway.py      # HTTP Gateway (FastAPI)
├── docker-compose.yml          # Docker Compose config
├── Dockerfile.gateway          # Dockerfile cho gateway
└── README.md                   # This file
```

## Môi trường Variables

| Variable | Default | Mô tả |
|----------|---------|-------|
| `PANCAKE_API_KEY` | - | API key cho Pancake |
| `PANCAKE_MCP_URL` | http://pancake-mcp:8765 | URL của Pancake MCP |
| `GATEWAY_PORT` | 8766 | Port của gateway |

## Troubleshooting

### Kiểm tra logs

```bash
# Gateway logs
docker logs pancake-mcp-gateway

# MCP server logs
docker logs pancake-mcp-server
```

### Restart services

```bash
docker compose restart
```

### Kiểm tra kết nối

```bash
# Từ gateway container
docker exec -it pancake-mcp-gateway curl http://pancake-mcp:8765/health
```

## Tích hợp với OpenClaw

Hiện tại OpenClaw chưa hỗ trợ MCP client natively, nhưng bạn có thể:

1. **Sử dụng HTTP calls**: OpenClaw có thể gọi HTTP endpoints của gateway
2. **Tạo custom skill**: Viết một skill cho OpenClaw sử dụng HTTP API
3. **Chờ MCP support**: OpenClaw đang phát triển MCP client (theo dõi PRs)

### Ví dụ sử dụng trong OpenClaw

```
User: "Tìm đơn hàng hôm nay"
OpenClaw: [Gọi http://localhost:8766/orders?start_date=today]
          [Trả về danh sách đơn hàng]

User: "Gửi tin nhắn cho khách hàng đơn #123456"
OpenClaw: [Gọi POST /conversations/xxx/messages]
          [Xác nhận đã gửi]
```

## Liên kết

- [Pancake MCP Server](/cowork_mcp/pancake-mcp-server/)
- [OpenClaw Docs](https://docs.openclaw.ai/)
- [OpenClaw MCP Issues](https://github.com/openclaw/openclaw/issues?q=is%3Aissue+mcp)

## Lưu ý

- Cần có `PANCAKE_API_KEY` để sử dụng đầy đủ tính năng
- Gateway chuyển đổi REST API thành MCP tool calls
- OpenClaw MCP support đang được phát triển