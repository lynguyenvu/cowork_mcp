# Pancake MCP Skill for OpenClaw

## Description

Query and manage Pancake POS system for Vietnamese e-commerce businesses. This skill enables OpenClaw to interact with Pancake POS API for order management, inventory tracking, shipping arrangements, and customer conversations.

## Capabilities

- **Shop Management**: Get shop information, provinces, districts, communes
- **Order Management**: Search orders, create orders, update orders, get order details
- **Inventory Management**: List warehouses, manage inventory
- **Shipping Management**: Arrange shipments, track orders, handle returns
- **Customer Conversations**: List conversations, send messages, manage customer communications
- **File Attachments**: Download attachments, extract text from images

## Configuration

Requires `PANCAKE_API_KEY` for POS features (orders, inventory, shipping).
For chat/conversation features only, use `PANCAKE_ACCESS_TOKEN` instead.

```json
{
  "pancake-mcp": {
    "apiKey": "your_pancake_api_key",
    "accessToken": "your_chat_access_token"
  }
}
```

## Tools

### Shop Tools
- `pancake_get_shops` - Get all shops associated with the account
- `pancake_get_provinces` - Get list of provinces
- `pancake_get_districts` - Get districts for a province
- `pancake_get_communes` - Get communes for a district

### Order Tools
- `pancake_search_orders` - Search orders with filters
- `pancake_get_order` - Get detailed order information
- `pancake_create_order` - Create a new order
- `pancake_update_order` - Update an existing order
- `pancake_get_order_tags` - Get available order tags
- `pancake_get_order_sources` - Get order sources

### Inventory Tools
- `pancake_list_warehouses` - List all warehouses
- `pancake_create_warehouse` - Create a new warehouse
- `pancake_update_warehouse` - Update warehouse information
- `pancake_get_inventory_history` - Get inventory history

### Shipping Tools
- `pancake_arrange_shipment` - Arrange shipment for an order
- `pancake_get_tracking_url` - Get tracking URL for a shipment
- `pancake_list_return_orders` - List return orders
- `pancake_create_return_order` - Create a return order

### Conversation Tools
- `pancake_list_conversations` - List customer conversations
- `pancake_get_conversation` - Get conversation details
- `pancake_get_messages` - Get messages in a conversation
- `pancake_send_message` - Send a message to customer
- `pancake_update_conversation` - Update conversation status

### Attachment Tools
- `pancake_list_message_attachment` - List attachments in a message
- `pancake_download_attachment` - Download an attachment
- `pancake_preview_attachment_content` - Preview attachment content
- `pancake_extract_text_from_image` - Extract text from image attachments

## Usage Examples

### Search Orders
```
Search for orders from last week with status "confirmed"
```

### Create Order
```
Create a new order for customer Nguyen Van A, phone 0901234567, address in District 1, HCMC
```

### Arrange Shipment
```
Arrange shipment for order #123456 using GHN
```

### Check Conversations
```
List unread conversations from today
```

## API Documentation

- Pancake POS API: https://docs.pancake.vn/
- Pancake MCP Server: /cowork_mcp/pancake-mcp-server/

## Notes

- This skill requires the Pancake MCP server to be running
- Default endpoint: http://localhost:8765
- Supports both HTTP and stdio transport modes
- Rate limits apply based on Pancake API quotas

## Author

Claude Code

## License

MIT