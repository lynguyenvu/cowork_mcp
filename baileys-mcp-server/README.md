# WhatsApp MCP Server

Kết nối Claude với WhatsApp thông qua MCP — cho phép Claude gửi tin nhắn, quản lý nhóm và kiểm tra trạng thái kết nối.

> Sử dụng [Baileys](https://github.com/WhiskeySockets/Baileys) — thư viện WhatsApp Web API không chính thức cho Node.js/TypeScript.

---

## Tính năng

- **21 MCP tools** — nhắn tin, quản lý nhóm, kiểm tra kết nối
- **Xác thực QR Code** — quét QR lần đầu, tự động kết nối lại từ lần sau
- **Lưu phiên** — credentials lưu vào `./auth_info/`, không cần quét lại
- **stdio transport** — tích hợp trực tiếp với Claude Desktop

---

## 21 Tools MCP

| Module | Tool |
|--------|------|
| Kết nối | `whatsapp_get_status`, `whatsapp_logout` |
| Nhắn tin | `whatsapp_send_text`, `whatsapp_send_image`, `whatsapp_send_document`, `whatsapp_send_audio`, `whatsapp_send_video`, `whatsapp_send_reaction`, `whatsapp_send_poll`, `whatsapp_delete_message`, `whatsapp_get_messages`, `whatsapp_check_number` |
| Nhóm | `whatsapp_list_groups`, `whatsapp_get_group_info`, `whatsapp_create_group`, `whatsapp_add_participants`, `whatsapp_remove_participants`, `whatsapp_update_group_subject`, `whatsapp_update_group_description`, `whatsapp_get_invite_link`, `whatsapp_leave_group` |

---

## Yêu cầu

- Node.js 18+
- Tài khoản WhatsApp hoạt động (cần điện thoại để quét QR lần đầu)

---

## Cài đặt

```bash
cd baileys-mcp-server
npm install
npm run build
```

---

## Chạy server

```bash
npm start
```

Lần đầu chạy, QR code sẽ hiển thị trong terminal. Mở WhatsApp trên điện thoại → **Thiết bị đã liên kết** → **Liên kết thiết bị** → quét QR.

Sau khi quét, credentials được lưu vào `./auth_info/`. Các lần khởi động tiếp theo sẽ tự kết nối lại.

---

## Tích hợp Claude Desktop

Thêm vào `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "node",
      "args": ["/đường/dẫn/tới/baileys-mcp-server/dist/index.js"]
    }
  }
}
```

**Lưu ý:** QR code xuất ra stderr, không ảnh hưởng đến giao thức stdio của MCP.

---

## Định dạng JID

| Loại | Định dạng | Ví dụ |
|------|-----------|-------|
| Người dùng | `{số điện thoại}@s.whatsapp.net` | `84987654321@s.whatsapp.net` |
| Nhóm | `{timestamp}-{hash}@g.us` | `1234567890-987654@g.us` |

Các tool nhận tin nhắn cũng chấp nhận số điện thoại thuần (VD: `84987654321`) và tự chuyển đổi sang JID.

---

## Cấu trúc Project

```
baileys-mcp-server/
├── src/
│   ├── index.ts          # MCP server entry point (stdio transport)
│   ├── constants.ts      # Hằng số dùng chung
│   ├── whatsapp.ts       # Baileys socket manager (singleton)
│   ├── store.ts          # In-memory message/chat store
│   ├── tools/
│   │   ├── index.ts      # Re-export tất cả tools
│   │   ├── connection.ts # Tools kết nối
│   │   ├── messaging.ts  # Tools nhắn tin
│   │   └── groups.ts     # Tools quản lý nhóm
│   └── utils/
│       └── index.ts      # Helper functions
├── dist/                 # Compiled JavaScript (sau khi build)
├── auth_info/            # WhatsApp session credentials (tự tạo)
├── package.json
└── tsconfig.json
```

---

## Lưu ý bảo mật

- `./auth_info/` chứa session credentials — **không commit vào git**
- Thêm `auth_info/` vào `.gitignore`
- Server chạy qua stdio — API key không rời khỏi máy bạn

---

## Tech Stack

| Thành phần | Mô tả |
|------------|-------|
| TypeScript 5.x | Ngôn ngữ |
| @whiskeysockets/baileys 6.x | WhatsApp Web API |
| @modelcontextprotocol/sdk | MCP framework |
| Zod | Schema validation |
| Pino | Logger (silent trong MCP mode) |
