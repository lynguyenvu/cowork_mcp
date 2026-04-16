# Beds24 MCP Skill for OpenClaw

## Description

Query and manage Beds24 property management system for hospitality businesses. This skill enables OpenClaw to interact with Beds24 API for booking management, property operations, room inventory, and availability tracking.

## Capabilities

- **Booking Management**: List, create, update, and cancel bookings
- **Property Management**: List properties, get details, manage rooms
- **Inventory Management**: Room availability, calendar management
- **Pricing**: Get pricing offers and availability calendar
- **Communications**: Guest messaging and booking communications

## Configuration

First-time setup: Generate an invite code from Beds24 and run beds24_setup_from_invite_code.
Save the returned refresh_token to your .env file.

```json
{
  "beds24-mcp": {
    "refreshToken": "your_refresh_token_here"
  }
}
```

**One-time setup flow:**
1. Generate invite code: https://beds24.com/control3.php?pagetype=apiv2
2. Call beds24_setup_from_invite_code with the code
3. Save the refresh_token to BEDS24_REFRESH_TOKEN env var

Access tokens are automatically obtained and refreshed from the refresh token.

## Tools

### Output Format

Most tools support an `response_format` parameter:
- `"markdown"` (default) – human-readable tables/text
- `"json"` – raw JSON, useful for programmatic processing or passing data between tools

### Booking Tools
- `beds24_list_bookings` - List bookings with filters
  - `property_id` - Filter by property ID
  - `status` - Filter by booking status (confirmed, pending, cancelled, inquiry)
  - `arrival` - Filter by specific arrival date (YYYY-MM-DD) - exact match
  - `arrivalFrom` - Filter by arrival date from (YYYY-MM-DD) - start of range
  - `arrivalTo` - Filter by arrival date to (YYYY-MM-DD) - end of range
  - `departure` - Filter by specific departure date (YYYY-MM-DD) - exact match
  - `departureFrom` - Departure date range start (YYYY-MM-DD)
  - `departureTo` - Departure date range end (YYYY-MM-DD)
  - `limit` - Max results per page (1-1000, default: 20)
  - `offset` - Pagination offset (use `next_offset` from previous response)
  - `compact` - Return essential fields only (id, status, arrival, departure, propertyId, unitId, totalPrice, currency, invoiceItems, bookingGroup). **Default: true. Always on unless you explicitly need full raw data.**
  - `include_invoice_items` - Include invoice items (default: true)
  - `include_info_items` - Include info items (default: false)
  - `include_booking_group` - Include booking group data (default: true)
  - `response_format` - `"markdown"` or `"json"` (default: markdown)

**⚠️ LARGE RESULT SETS - MANDATORY STRATEGY:**
When fetching >50 bookings (e.g., full month, all properties), ALWAYS use:
1. `compact: true` — reduces each booking from ~3KB to ~200 bytes, fits 500+ bookings per response
2. `limit: 100` — fetch max per call
3. Loop with `offset` using `next_offset` from response until `has_more: false`
4. For specific booking details, call `beds24_get_booking` individually after filtering

Example for full month retrieval:
```
beds24_list_bookings(arrivalFrom: "2026-03-01", arrivalTo: "2026-03-31", limit: 100, offset: 0)
→ compact: true is default — no need to specify
→ if has_more: true → call again with offset: <next_offset>
```

**Date Filter Notes:**
- Use `arrival` for exact date (e.g., `"arrival": "2026-03-18"`)
- Use `arrivalFrom` + `arrivalTo` for date range (e.g., `"arrivalFrom": "2026-03-18", "arrivalTo": "2026-03-25"`)
- Same pattern applies for `departure`, `departureFrom`, `departureTo`
- `beds24_get_booking` - Get booking details by ID
  - `response_format` - `"markdown"` or `"json"`
- `beds24_create_booking` - Create a new booking
- `beds24_update_booking` - Update an existing booking
  - `booking_id` - Booking ID to update (required)
  - `guest_name`, `guest_email`, `guest_phone` - Update guest info
  - `check_in`, `check_out` - Update dates (YYYY-MM-DD)
  - `number_of_guests` - Update guest count
  - `status` - Update booking status (e.g. confirmed, cancelled)
  - `special_requests` - Update notes
  - `invoice_items` - Create or update invoice items: `[{id?, type?, description?, qty?, amount?, lineTotal?}]`
    - Omit `id` to **create** a new item (`type` required: `"charge"` or `"payment"`)
    - Include `id` to **update** an existing item
  - `response_format` - `"markdown"` or `"json"`
- `beds24_cancel_booking` - Cancel a booking

### Property Tools
- `beds24_list_properties` - List all properties
  - `response_format` - `"markdown"` or `"json"`
- `beds24_get_property` - Get property details
  - `response_format` - `"markdown"` or `"json"`
- `beds24_list_property_rooms` - List rooms in a property
  - `response_format` - `"markdown"` or `"json"`

### Availability Tools
- `beds24_check_availability` - Check room availability for dates
  - `response_format` - `"markdown"` or `"json"`
- `beds24_get_calendar` - Get availability calendar
  - `response_format` - `"markdown"` or `"json"`
- `beds24_update_calendar` - Update calendar availability

### Pricing Tools
- `beds24_get_pricing_offers` - Get pricing offers for dates
  - `response_format` - `"markdown"` or `"json"`

## Usage Examples

### List Bookings
```
List bookings with arrival date 2026-03-18
List bookings with arrivalFrom 2026-03-18 and arrivalTo 2026-03-20
List bookings with departureFrom 2026-03-20 and departureTo 2026-03-25
Show 5 bookings with status confirmed
List bookings in JSON format (response_format: json)
```

### Get Booking Details
```
Get details for booking 83868227
Show booking ID 83868019
```

### Check Availability
```
Check availability for property 293252 from 2024-12-01 to 2024-12-05
```

### Create Booking
```
Create a booking for guest John Doe, property 293252, room 613457, check-in 2024-12-01, check-out 2024-12-03
```

### Cancel Booking
```
Cancel booking #12345 with reason "Guest requested"
```

## API Notes

- **Date Filters - IMPORTANT**: Beds24 API uses these exact parameter names:
  - `arrival` - Exact arrival date (YYYY-MM-DD)
  - `arrivalFrom` - Arrival date range start (YYYY-MM-DD)
  - `arrivalTo` - Arrival date range end (YYYY-MM-DD)
  - `departure` - Exact departure date (YYYY-MM-DD)
  - `departureFrom` - Departure date range start (YYYY-MM-DD)
  - `departureTo` - Departure date range end (YYYY-MM-DD)

  DO NOT use `checkInAfter`/`checkInBefore` - these are NOT valid Beds24 parameters.

- Get booking uses query param `?id=xxx` (not path param `/bookings/xxx`)
- API returns max 100 per request; use `offset` + `next_offset` to paginate
- **Always use `compact: true` for large result sets to avoid truncation**
- Response structure: `{success: true, data: [...], count: N}`

## Health Check

- Endpoint: `GET /health`
- Response: `{"status": "ok", "server": "beds24-mcp"}`

## API Documentation

- Beds24 API v2: https://api.beds24.com/v2/
- Beds24 MCP Server: /cowork_mcp/beds24-mcp-server/

## Notes

- This skill requires the Beds24 MCP server to be running
- Endpoint (Docker network): `http://beds24-mcp-server:8001`
- Endpoint (host): `http://localhost:8001`
- Health check: `http://beds24-mcp-server:8001/health`
- Agent không cần truyền token — server tự quản lý từ BEDS24_REFRESH_TOKEN env var
- Supports both HTTP and stdio transport modes
- Rate limits apply based on Beds24 API quotas

## Author

Claude Code

## License

MIT