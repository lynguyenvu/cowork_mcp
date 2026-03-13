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

### Booking Tools
- `beds24_list_bookings` - List bookings with filters (property, status, dates)
- `beds24_get_booking` - Get booking details by ID
- `beds24_create_booking` - Create a new booking
- `beds24_update_booking` - Update an existing booking
- `beds24_cancel_booking` - Cancel a booking

### Property Tools
- `beds24_list_properties` - List all properties
- `beds24_get_property` - Get property details
- `beds24_list_property_rooms` - List rooms in a property

### Availability Tools
- `beds24_check_availability` - Check room availability for dates
- `beds24_get_calendar` - Get availability calendar
- `beds24_update_calendar` - Update calendar availability

### Pricing Tools
- `beds24_get_pricing_offers` - Get pricing offers for dates

## Usage Examples

### List Bookings
```
List all bookings for this week
```

### Check Availability
```
Check availability for property ABC123 from 2024-12-01 to 2024-12-05
```

### Create Booking
```
Create a booking for guest John Doe, property ABC123, room XYZ, check-in 2024-12-01, check-out 2024-12-03
```

### Cancel Booking
```
Cancel booking #12345 with reason "Guest requested"
```

## API Documentation

- Beds24 API v2: https://api.beds24.com/v2/
- Beds24 MCP Server: /cowork_mcp/beds24-mcp-server/

## Notes

- This skill requires the Beds24 MCP server to be running
- Default endpoint: http://localhost:8761
- API authentication uses Bearer token in Authorization header
- Supports both HTTP and stdio transport modes
- Rate limits apply based on Beds24 API quotas

## Author

Claude Code

## License

MIT