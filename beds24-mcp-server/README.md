# Beds24 MCP Server

MCP (Model Context Protocol) server for Beds24 API v2 - Enables LLMs to interact with Beds24 property management system for booking management, property management, and inventory/pricing.

## Features

This MCP server provides comprehensive tools for managing:
- **Bookings**: Create, read, update, cancel bookings and manage booking communications
- **Properties**: Manage properties and rooms information
- **Inventory & Pricing**: Check availability, manage calendar, and pricing

## Installation

```bash
cd beds24-mcp-server
pip install -r requirements.txt
```

## Configuration

Set the following environment variables:

```bash
# API Token (Long life token or refresh token)
export BEDS24_API_TOKEN="your_api_token_here"

# Optional: API Base URL (defaults to production)
export BEDS24_API_BASE_URL="https://api.beds24.com/v2"
```

## Authentication

Beds24 API v2 supports two authentication methods:

1. **Long Life Tokens**: Read-only access, never expire if used within 90 days
2. **Refresh Tokens**: Read/write access, expire after 30 days of inactivity

Generate your token from Beds24 dashboard and set it in the `BEDS24_API_TOKEN` environment variable.

## Usage

### Run as STDIO server (for local development/testing):

```bash
python server.py
```

### Run as HTTP server (for production):

```bash
python server.py --transport streamable-http --port 8000
```

### Run as SSE server:

```bash
python server.py --transport sse --port 8000
```

## Available Tools

### Booking Management
- `beds24_list_bookings` - List bookings with filters
- `beds24_get_booking` - Get booking details by ID
- `beds24_create_booking` - Create a new booking
- `beds24_update_booking` - Update existing booking
- `beds24_cancel_booking` - Cancel a booking
- `beds24_list_booking_messages` - Get booking messages
- `beds24_send_booking_message` - Send message to guest

### Property Management
- `beds24_list_properties` - List all properties
- `beds24_get_property` - Get property details
- `beds24_list_property_rooms` - List rooms for a property
- `beds24_update_property` - Update property information

### Inventory & Pricing
- `beds24_check_availability` - Check room availability for dates
- `beds24_get_calendar` - Get calendar values for rooms
- `beds24_update_calendar` - Update calendar (prices/availability)
- `beds24_get_pricing_offers` - Get pricing offers

## Response Formats

All tools support two response formats:
- **markdown** (default): Human-readable formatted output
- **json**: Machine-readable structured data

Example:
```python
beds24_list_bookings(
    limit=20,
    offset=0,
    response_format="json"  # or "markdown"
)
```

## Pagination

Tools that return lists support pagination:
- `limit`: Maximum results (default: 20, max: 100)
- `offset`: Number of results to skip (default: 0)

Response includes pagination metadata:
```json
{
  "total": 150,
  "count": 20,
  "offset": 0,
  "has_more": true,
  "next_offset": 20
}
```

## Character Limits

To prevent overwhelming responses:
- Maximum response size: 25,000 characters
- Responses are truncated with clear notice if exceeded
- Use filters and pagination to manage large result sets

## Error Handling

All tools provide clear, actionable error messages:
- **404**: "Resource not found. Please check the ID is correct."
- **403**: "Permission denied. You don't have access to this resource."
- **429**: "Rate limit exceeded. Please wait before making more requests."
- **Timeout**: "Request timed out. Please try again."

## Rate Limiting

Beds24 API uses a credit system:
- Default: 100 credits per 5 minutes
- Each API call consumes credits based on complexity
- 429 errors indicate rate limit exceeded

## Examples

### List recent bookings
```python
beds24_list_bookings(limit=10, status="confirmed")
```

### Create a new booking
```python
beds24_create_booking(
    property_id="12345",
    check_in="2024-03-15",
    check_out="2024-03-20",
    guest_name="John Doe",
    guest_email="john@example.com",
    room_type="deluxe"
)
```

### Check availability
```python
beds24_check_availability(
    property_id="12345",
    check_in="2024-03-15",
    check_out="2024-03-20"
)
```

## Development

### Testing

Run the server locally:
```bash
python server.py
```

### Building

For production deployment with HTTP transport:
```bash
python server.py --transport streamable-http --port 8000
```

## Support

For issues or questions:
- Beds24 API Documentation: https://wiki.beds24.com/index.php/Category:API_V2
- MCP Protocol: https://modelcontextprotocol.io

## License

MIT License - See LICENSE file for details
