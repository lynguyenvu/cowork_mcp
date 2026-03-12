#!/usr/bin/env python3
"""
Beds24 MCP Server - Model Context Protocol server for Beds24 API v2.

This server enables LLMs to interact with Beds24 property management system
for comprehensive booking, property, and inventory management.

Features:
- Booking Management: Create, read, update, cancel bookings
- Property Management: Manage properties and rooms
- Inventory & Pricing: Availability, calendar, pricing management
- Booking Communications: Send and receive messages with guests

Authentication:
- Supports Long Life Tokens (read-only) and Refresh Tokens (read/write)
- Token must be set in BEDS24_API_TOKEN environment variable

Author: Claude Code
"""

import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP, Context

# Initialize MCP server
mcp = FastMCP("beds24_mcp")

# ==============================================================================
# Constants and Configuration
# ==============================================================================

API_BASE_URL = os.getenv("BEDS24_API_BASE_URL", "https://api.beds24.com/v2")
API_TOKEN = os.getenv("BEDS24_API_TOKEN")
CHARACTER_LIMIT = 25000  # Maximum response size in characters

# ==============================================================================
# Response Format Enum
# ==============================================================================

class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# ==============================================================================
# Error Handling Utilities
# ==============================================================================

def _handle_api_error(e: Exception) -> str:
    """Consistent error formatting across all tools."""
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 404:
            return "Error: Resource not found. Please check the ID is correct."
        elif e.response.status_code == 403:
            return "Error: Permission denied. You don't have access to this resource."
        elif e.response.status_code == 401:
            return "Error: Invalid API authentication. Please check your API token."
        elif e.response.status_code == 429:
            return "Error: Rate limit exceeded. Please wait before making more requests."
        elif e.response.status_code == 400:
            try:
                error_data = e.response.json()
                return f"Error: Invalid request - {error_data.get('error', 'Bad request')}"
            except:
                return "Error: Invalid request parameters."
        return f"Error: API request failed with status {e.response.status_code}"
    elif isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Please try again."
    elif isinstance(e, httpx.ConnectError):
        return "Error: Failed to connect to Beds24 API. Please check your network connection."
    return f"Error: Unexpected error occurred: {type(e).__name__}"


async def _make_api_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Reusable function for all API calls with proper error handling.

    Args:
        endpoint: API endpoint path (e.g., "bookings", "properties")
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        params: Query parameters for GET requests
        json_data: JSON payload for POST/PUT/PATCH requests
        **kwargs: Additional httpx client arguments

    Returns:
        Dict containing API response data

    Raises:
        httpx.HTTPStatusError: For HTTP error responses
        httpx.TimeoutException: For request timeouts
    """
    if not API_TOKEN:
        raise ValueError(
            "BEDS24_API_TOKEN environment variable is not set. "
            "Please set it before running the server."
        )

    headers = {
        "Authorization": f"token: {API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{API_BASE_URL}/{endpoint}",
            headers=headers,
            params=params,
            json=json_data,
            timeout=30.0,
            **kwargs
        )
        response.raise_for_status()
        return response.json()


# ==============================================================================
# Input Validation Models
# ==============================================================================

class ListBookingsInput(BaseModel):
    """Input model for listing bookings."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    property_id: Optional[str] = Field(
        default=None,
        description="Filter by property ID (e.g., '12345', '67890')",
        min_length=1,
        max_length=50
    )
    status: Optional[str] = Field(
        default=None,
        description="Filter by booking status (e.g., 'confirmed', 'pending', 'cancelled')",
        min_length=1,
        max_length=50
    )
    check_in_after: Optional[str] = Field(
        default=None,
        description="Filter bookings with check-in date after this date (format: YYYY-MM-DD, e.g., '2024-03-15')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    check_in_before: Optional[str] = Field(
        default=None,
        description="Filter bookings with check-in date before this date (format: YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    limit: Optional[int] = Field(
        default=20,
        description="Maximum number of bookings to return (range: 1-100)",
        ge=1,
        le=100
    )
    offset: Optional[int] = Field(
        default=0,
        description="Number of results to skip for pagination (must be >= 0)",
        ge=0
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class GetBookingInput(BaseModel):
    """Input model for getting a specific booking."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    booking_id: str = Field(
        ...,
        description="The unique booking ID (e.g., 'BOOK-12345', '67890')",
        min_length=1,
        max_length=100
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class CreateBookingInput(BaseModel):
    """Input model for creating a new booking."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    property_id: str = Field(
        ...,
        description="The property ID where booking will be created (e.g., '12345')",
        min_length=1,
        max_length=50
    )
    room_id: Optional[str] = Field(
        default=None,
        description="Specific room ID to book (e.g., 'ROOM-123'). If not provided, system will assign available room.",
        min_length=1,
        max_length=100
    )
    check_in: str = Field(
        ...,
        description="Check-in date (format: YYYY-MM-DD, e.g., '2024-03-15')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    check_out: str = Field(
        ...,
        description="Check-out date (format: YYYY-MM-DD, e.g., '2024-03-20')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    guest_name: str = Field(
        ...,
        description="Guest's full name (e.g., 'John Doe', 'Jane Smith')",
        min_length=1,
        max_length=200
    )
    guest_email: str = Field(
        ...,
        description="Guest's email address (e.g., 'john@example.com')",
        pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$'
    )
    guest_phone: Optional[str] = Field(
        default=None,
        description="Guest's phone number (e.g., '+1234567890')",
        min_length=1,
        max_length=50
    )
    number_of_guests: Optional[int] = Field(
        default=1,
        description="Number of guests (must be >= 1)",
        ge=1
    )
    special_requests: Optional[str] = Field(
        default=None,
        description="Special requests or notes from guest (e.g., 'High floor room preferred', 'Allergy to pets')",
        max_length=1000
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )

    @field_validator('check_out')
    @classmethod
    def validate_dates(cls, v: str, info) -> str:
        """Validate that check-out is after check-in."""
        check_in = info.data.get('check_in')
        if check_in and v:
            if v <= check_in:
                raise ValueError("Check-out date must be after check-in date")
        return v


class UpdateBookingInput(BaseModel):
    """Input model for updating an existing booking."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    booking_id: str = Field(
        ...,
        description="The booking ID to update (e.g., 'BOOK-12345')",
        min_length=1,
        max_length=100
    )
    guest_name: Optional[str] = Field(
        default=None,
        description="Updated guest name (e.g., 'John Doe')",
        min_length=1,
        max_length=200
    )
    guest_email: Optional[str] = Field(
        default=None,
        description="Updated guest email (e.g., 'john@example.com')",
        pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$'
    )
    guest_phone: Optional[str] = Field(
        default=None,
        description="Updated guest phone number (e.g., '+1234567890')",
        min_length=1,
        max_length=50
    )
    number_of_guests: Optional[int] = Field(
        default=None,
        description="Updated number of guests (must be >= 1)",
        ge=1
    )
    check_in: Optional[str] = Field(
        default=None,
        description="Updated check-in date (format: YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    check_out: Optional[str] = Field(
        default=None,
        description="Updated check-out date (format: YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    special_requests: Optional[str] = Field(
        default=None,
        description="Updated special requests (max 1000 characters)",
        max_length=1000
    )
    status: Optional[str] = Field(
        default=None,
        description="Updated booking status (e.g., 'confirmed', 'cancelled')",
        min_length=1,
        max_length=50
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class CancelBookingInput(BaseModel):
    """Input model for cancelling a booking."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    booking_id: str = Field(
        ...,
        description="The booking ID to cancel (e.g., 'BOOK-12345')",
        min_length=1,
        max_length=100
    )
    cancellation_reason: Optional[str] = Field(
        default=None,
        description="Reason for cancellation (e.g., 'Guest request', 'Double booking')",
        max_length=500
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class ListBookingMessagesInput(BaseModel):
    """Input model for listing booking messages."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    booking_id: str = Field(
        ...,
        description="The booking ID to get messages for (e.g., 'BOOK-12345')",
        min_length=1,
        max_length=100
    )
    limit: Optional[int] = Field(
        default=50,
        description="Maximum number of messages to return (range: 1-100)",
        ge=1,
        le=100
    )
    offset: Optional[int] = Field(
        default=0,
        description="Number of results to skip for pagination (must be >= 0)",
        ge=0
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class SendBookingMessageInput(BaseModel):
    """Input model for sending a booking message."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    booking_id: str = Field(
        ...,
        description="The booking ID to send message to (e.g., 'BOOK-12345')",
        min_length=1,
        max_length=100
    )
    message: str = Field(
        ...,
        description="Message content to send to guest (e.g., 'Your room is ready', 'Check-in instructions')",
        min_length=1,
        max_length=2000
    )
    message_type: Optional[str] = Field(
        default="general",
        description="Type of message (e.g., 'general', 'pre-arrival', 'post-departure', 'confirmation')",
        min_length=1,
        max_length=50
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class ListPropertiesInput(BaseModel):
    """Input model for listing properties."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    limit: Optional[int] = Field(
        default=20,
        description="Maximum number of properties to return (range: 1-100)",
        ge=1,
        le=100
    )
    offset: Optional[int] = Field(
        default=0,
        description="Number of results to skip for pagination (must be >= 0)",
        ge=0
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class GetPropertyInput(BaseModel):
    """Input model for getting a specific property."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    property_id: str = Field(
        ...,
        description="The property ID (e.g., '12345', 'PROP-67890')",
        min_length=1,
        max_length=100
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class ListPropertyRoomsInput(BaseModel):
    """Input model for listing property rooms."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    property_id: str = Field(
        ...,
        description="The property ID to get rooms for (e.g., '12345')",
        min_length=1,
        max_length=100
    )
    room_type: Optional[str] = Field(
        default=None,
        description="Filter by room type (e.g., 'deluxe', 'standard', 'suite')",
        min_length=1,
        max_length=100
    )
    limit: Optional[int] = Field(
        default=50,
        description="Maximum number of rooms to return (range: 1-100)",
        ge=1,
        le=100
    )
    offset: Optional[int] = Field(
        default=0,
        description="Number of results to skip for pagination (must be >= 0)",
        ge=0
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class CheckAvailabilityInput(BaseModel):
    """Input model for checking room availability."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    property_id: str = Field(
        ...,
        description="The property ID to check availability for (e.g., '12345')",
        min_length=1,
        max_length=100
    )
    check_in: str = Field(
        ...,
        description="Check-in date (format: YYYY-MM-DD, e.g., '2024-03-15')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    check_out: str = Field(
        ...,
        description="Check-out date (format: YYYY-MM-DD, e.g., '2024-03-20')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    room_type: Optional[str] = Field(
        default=None,
        description="Specific room type to check (e.g., 'deluxe', 'standard'). If not provided, checks all room types.",
        min_length=1,
        max_length=100
    )
    number_of_guests: Optional[int] = Field(
        default=1,
        description="Number of guests (must be >= 1)",
        ge=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )

    @field_validator('check_out')
    @classmethod
    def validate_dates(cls, v: str, info) -> str:
        """Validate that check-out is after check-in."""
        check_in = info.data.get('check_in')
        if check_in and v:
            if v <= check_in:
                raise ValueError("Check-out date must be after check-in date")
        return v


class GetCalendarInput(BaseModel):
    """Input model for getting calendar values."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    property_id: str = Field(
        ...,
        description="The property ID (e.g., '12345')",
        min_length=1,
        max_length=100
    )
    room_id: Optional[str] = Field(
        default=None,
        description="Specific room ID. If not provided, returns calendar for all rooms in property.",
        min_length=1,
        max_length=100
    )
    start_date: str = Field(
        ...,
        description="Start date for calendar (format: YYYY-MM-DD, e.g., '2024-03-01')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end_date: str = Field(
        ...,
        description="End date for calendar (format: YYYY-MM-DD, e.g., '2024-03-31')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class UpdateCalendarInput(BaseModel):
    """Input model for updating calendar values."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    property_id: str = Field(
        ...,
        description="The property ID (e.g., '12345')",
        min_length=1,
        max_length=100
    )
    room_id: Optional[str] = Field(
        default=None,
        description="Specific room ID to update. If not provided, updates apply to all rooms.",
        min_length=1,
        max_length=100
    )
    date: str = Field(
        ...,
        description="Date to update (format: YYYY-MM-DD, e.g., '2024-03-15')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    price: Optional[float] = Field(
        default=None,
        description="Updated price for the date (e.g., 149.99, 200.00)",
        ge=0
    )
    availability: Optional[bool] = Field(
        default=None,
        description="Set availability status: true = available, false = not available"
    )
    minimum_stay: Optional[int] = Field(
        default=None,
        description="Minimum stay requirement in nights (must be >= 1)",
        ge=1
    )
    maximum_stay: Optional[int] = Field(
        default=None,
        description="Maximum stay limit in nights (must be >= 1)",
        ge=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class GetPricingOffersInput(BaseModel):
    """Input model for getting pricing offers."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    property_id: str = Field(
        ...,
        description="The property ID (e.g., '12345')",
        min_length=1,
        max_length=100
    )
    check_in: str = Field(
        ...,
        description="Check-in date (format: YYYY-MM-DD, e.g., '2024-03-15')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    check_out: str = Field(
        ...,
        description="Check-out date (format: YYYY-MM-DD, e.g., '2024-03-20')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    number_of_guests: Optional[int] = Field(
        default=1,
        description="Number of guests (must be >= 1)",
        ge=1
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


# ==============================================================================
# Response Formatting Utilities
# ==============================================================================

def _format_timestamp(timestamp: Any) -> str:
    """
    Convert timestamp to human-readable format.

    Args:
        timestamp: Unix timestamp, ISO string, or datetime object

    Returns:
        Human-readable date/time string
    """
    try:
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        elif isinstance(timestamp, datetime):
            dt = timestamp
        else:
            return str(timestamp)

        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except:
        return str(timestamp)


def _format_markdown_booking(booking: Dict[str, Any]) -> str:
    """
    Format a booking as markdown for human-readable output.

    Args:
        booking: Booking data dictionary

    Returns:
        Formatted markdown string
    """
    lines = []

    # Header
    booking_id = booking.get('id', 'N/A')
    status = booking.get('status', 'unknown').upper()
    lines.append(f"## Booking {booking_id} - Status: {status}")
    lines.append("")

    # Dates
    if 'checkIn' in booking or 'check_in' in booking:
        check_in = booking.get('checkIn') or booking.get('check_in', 'N/A')
        check_out = booking.get('checkOut') or booking.get('check_out', 'N/A')
        lines.append(f"**Check-in:** {check_in}")
        lines.append(f"**Check-out:** {check_out}")
        lines.append("")

    # Guest Information
    if 'guest' in booking or 'guestName' in booking:
        lines.append("### Guest Information")
        guest_name = booking.get('guestName') or booking.get('guest', {}).get('name', 'N/A')
        guest_email = booking.get('guestEmail') or booking.get('guest', {}).get('email', 'N/A')
        guest_phone = booking.get('guestPhone') or booking.get('guest', {}).get('phone', 'N/A')

        lines.append(f"- **Name:** {guest_name}")
        lines.append(f"- **Email:** {guest_email}")
        if guest_phone:
            lines.append(f"- **Phone:** {guest_phone}")
        lines.append("")

    # Property & Room
    if 'property' in booking or 'propertyId' in booking:
        lines.append("### Property & Room")
        property_name = booking.get('propertyName') or booking.get('property', {}).get('name', 'N/A')
        room_name = booking.get('roomName') or booking.get('room', {}).get('name', 'N/A')

        lines.append(f"- **Property:** {property_name}")
        lines.append(f"- **Room:** {room_name}")
        lines.append("")

    # Additional Details
    if 'numberOfGuests' in booking or 'numberOfGuests' in booking:
        num_guests = booking.get('numberOfGuests') or booking.get('numberOfGuests', 'N/A')
        lines.append(f"**Number of Guests:** {num_guests}")

    if 'specialRequests' in booking or 'specialRequests' in booking:
        special_requests = booking.get('specialRequests') or booking.get('specialRequests', '')
        if special_requests:
            lines.append(f"**Special Requests:** {special_requests}")

    if 'totalPrice' in booking or 'totalPrice' in booking:
        total_price = booking.get('totalPrice') or booking.get('totalPrice', 'N/A')
        lines.append(f"**Total Price:** {total_price}")

    lines.append("")

    return "\n".join(lines)


def _format_markdown_property(property_data: Dict[str, Any]) -> str:
    """
    Format a property as markdown for human-readable output.

    Args:
        property_data: Property data dictionary

    Returns:
        Formatted markdown string
    """
    lines = []

    # Header
    property_id = property_data.get('id', 'N/A')
    property_name = property_data.get('name', 'N/A')
    lines.append(f"## Property {property_name} (ID: {property_id})")
    lines.append("")

    # Basic Info
    if 'address' in property_data:
        address = property_data['address']
        lines.append("### Address")
        lines.append(f"- **Street:** {address.get('street', 'N/A')}")
        lines.append(f"- **City:** {address.get('city', 'N/A')}")
        lines.append(f"- **State/Province:** {address.get('state', 'N/A')}")
        lines.append(f"- **Postal Code:** {address.get('postalCode', 'N/A')}")
        lines.append(f"- **Country:** {address.get('country', 'N/A')}")
        lines.append("")

    # Contact Info
    if 'contact' in property_data or 'email' in property_data:
        lines.append("### Contact Information")
        email = property_data.get('email', property_data.get('contact', {}).get('email', 'N/A'))
        phone = property_data.get('phone', property_data.get('contact', {}).get('phone', 'N/A'))
        lines.append(f"- **Email:** {email}")
        if phone:
            lines.append(f"- **Phone:** {phone}")
        lines.append("")

    # Additional Details
    if 'description' in property_data:
        lines.append("### Description")
        lines.append(property_data['description'])
        lines.append("")

    if 'amenities' in property_data:
        lines.append("### Amenities")
        for amenity in property_data['amenities']:
            lines.append(f"- {amenity}")
        lines.append("")

    return "\n".join(lines)


def _format_markdown_room(room: Dict[str, Any]) -> str:
    """
    Format a room as markdown for human-readable output.

    Args:
        room: Room data dictionary

    Returns:
        Formatted markdown string
    """
    lines = []

    room_id = room.get('id', 'N/A')
    room_name = room.get('name', 'N/A')
    room_type = room.get('type', 'N/A')

    lines.append(f"- **{room_name}** (ID: {room_id}, Type: {room_type})")

    if 'capacity' in room:
        lines.append(f"  - Capacity: {room['capacity']} guests")
    if 'price' in room:
        lines.append(f"  - Price: {room['price']}")
    if 'amenities' in room:
        lines.append(f"  - Amenities: {', '.join(room['amenities'])}")

    lines.append("")

    return "\n".join(lines)


def _format_markdown_availability(availability: Dict[str, Any]) -> str:
    """
    Format availability data as markdown.

    Args:
        availability: Availability data dictionary

    Returns:
        Formatted markdown string
    """
    lines = []

    lines.append("## Availability Check Results")
    lines.append("")

    if 'available' in availability:
        available = availability['available']
        status = "✅ **Available**" if available else "❌ **Not Available**"
        lines.append(status)
        lines.append("")

    if 'available_rooms' in availability or 'availableRooms' in availability:
        rooms = availability.get('available_rooms') or availability.get('availableRooms', [])
        if rooms:
            lines.append(f"**Available Rooms ({len(rooms)}):**")
            lines.append("")
            for room in rooms:
                lines.append(_format_markdown_room(room))
        else:
            lines.append("❌ No rooms available for the requested dates.")

    if 'price_range' in availability or 'priceRange' in availability:
        price_range = availability.get('price_range') or availability.get('priceRange', {})
        lines.append("### Price Information")
        if 'min' in price_range:
            lines.append(f"- **Minimum Price:** {price_range['min']}")
        if 'max' in price_range:
            lines.append(f"- **Maximum Price:** {price_range['max']}")
        lines.append("")

    return "\n".join(lines)


def _format_markdown_calendar(calendar_data: Dict[str, Any]) -> str:
    """
    Format calendar data as markdown.

    Args:
        calendar_data: Calendar data dictionary

    Returns:
        Formatted markdown string
    """
    lines = []

    lines.append("## Calendar Data")
    lines.append("")

    if 'dates' in calendar_data:
        dates = calendar_data['dates']
        lines.append(f"**Total Dates:** {len(dates)}")
        lines.append("")

        # Show first 10 dates
        for date_data in dates[:10]:
            date = date_data.get('date', 'N/A')
            price = date_data.get('price', 'N/A')
            available = date_data.get('available', False)
            status = "✅" if available else "❌"

            lines.append(f"- **{date}**: {status} Price: {price}")

        if len(dates) > 10:
            lines.append(f"\n... and {len(dates) - 10} more dates")

    return "\n".join(lines)


# ==============================================================================
# Tool Implementations - Booking Management
# ==============================================================================

@mcp.tool(
    name="beds24_list_bookings",
    annotations={
        "title": "List Bookings",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_list_bookings(params: ListBookingsInput) -> str:
    """
    List bookings from Beds24 with optional filters.

    This tool retrieves bookings with various filter options including property,
    status, and date ranges. It supports pagination for large result sets.

    Args:
        params (ListBookingsInput): Validated input parameters containing:
            - property_id (Optional[str]): Filter by specific property ID
            - status (Optional[str]): Filter by booking status (e.g., 'confirmed', 'pending')
            - check_in_after (Optional[str]): Filter bookings after this date (YYYY-MM-DD)
            - check_in_before (Optional[str]): Filter bookings before this date (YYYY-MM-DD)
            - limit (Optional[int]): Maximum results to return (default: 20, range: 1-100)
            - offset (Optional[int]): Pagination offset (default: 0)
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing booking list with the following schema:

        Success response (JSON format):
        {
            "total": int,              # Total number of bookings matching filters
            "count": int,              # Number of bookings in this response
            "offset": int,             # Current pagination offset
            "has_more": bool,          # Whether more results are available
            "next_offset": Optional[int],  # Offset for next page
            "bookings": [
                {
                    "id": str,         # Booking ID
                    "status": str,     # Booking status
                    "check_in": str,   # Check-in date
                    "check_out": str,  # Check-out date
                    "guest_name": str, # Guest name
                    "property_id": str,# Property ID
                    "total_price": float  # Total booking price
                }
            ]
        }

        Error response:
        "Error: <error message>" or "No bookings found matching criteria"

    Examples:
        - Use when: "List all confirmed bookings for property 12345"
        - Use when: "Show me bookings for next week"
        - Don't use when: You need details of a specific booking (use beds24_get_booking instead)
        - Don't use when: You want to create a new booking (use beds24_create_booking instead)

    Error Handling:
        - Input validation errors are handled by Pydantic model
        - Returns "Error: Rate limit exceeded" if too many requests (429 status)
        - Returns "Error: Invalid API authentication" if API token is invalid (401 status)
        - Returns "No bookings found matching criteria" if no results
    """
    try:
        # Build query parameters
        query_params = {}
        if params.property_id:
            query_params['propertyId'] = params.property_id
        if params.status:
            query_params['status'] = params.status
        if params.check_in_after:
            query_params['checkInAfter'] = params.check_in_after
        if params.check_in_before:
            query_params['checkInBefore'] = params.check_in_before
        if params.limit:
            query_params['limit'] = params.limit
        if params.offset:
            query_params['offset'] = params.offset

        # Make API request
        data = await _make_api_request("bookings", params=query_params)

        bookings = data.get('bookings', [])
        total = data.get('total', len(bookings))

        if not bookings:
            return "No bookings found matching criteria"

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = ["# Booking List", ""]
            lines.append(f"Total bookings: {total} (showing {len(bookings)} from offset {params.offset})")
            lines.append("")

            if total > params.limit + params.offset:
                lines.append(f"⚠️ More bookings available. Use offset={params.offset + params.limit} to see next page.")
                lines.append("")

            for booking in bookings:
                lines.append(_format_markdown_booking(booking))

            result = "\n".join(lines)
        else:
            # JSON format
            response = {
                "total": total,
                "count": len(bookings),
                "offset": params.offset,
                "has_more": total > params.offset + len(bookings),
                "next_offset": params.offset + len(bookings) if total > params.offset + len(bookings) else None,
                "bookings": bookings
            }
            result = json.dumps(response, indent=2)

        # Check character limit
        if len(result) > CHARACTER_LIMIT:
            return (
                f"Response truncated. Found {total} bookings but response exceeds {CHARACTER_LIMIT} character limit. "
                f"Use filters or reduce limit parameter to see fewer results."
            )

        return result

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_get_booking",
    annotations={
        "title": "Get Booking Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_get_booking(params: GetBookingInput) -> str:
    """
    Get detailed information about a specific booking.

    This tool retrieves complete booking details including guest information,
    room assignment, pricing, and special requests.

    Args:
        params (GetBookingInput): Validated input parameters containing:
            - booking_id (str): The unique booking ID (required)
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing booking details with the following schema:

        Success response (JSON format):
        {
            "id": str,                    # Booking ID
            "status": str,                # Current status
            "check_in": str,              # Check-in date (YYYY-MM-DD)
            "check_out": str,             # Check-out date (YYYY-MM-DD)
            "guest": {
                "name": str,              # Guest full name
                "email": str,             # Guest email
                "phone": Optional[str],   # Guest phone
                "special_requests": Optional[str]  # Special requests
            },
            "property": {
                "id": str,                # Property ID
                "name": str               # Property name
            },
            "room": {
                "id": str,                # Room ID
                "name": str,              # Room name
                "type": str               # Room type
            },
            "number_of_guests": int,      # Number of guests
            "total_price": float,         # Total price
            "created_at": str,            # Creation timestamp
            "updated_at": str             # Last update timestamp
        }

        Error response:
        "Error: Resource not found. Please check the booking ID is correct."

    Examples:
        - Use when: "Get details for booking BOOK-12345"
        - Use when: "Show me information about reservation 67890"
        - Don't use when: You want to list multiple bookings (use beds24_list_bookings instead)

    Error Handling:
        - Returns "Error: Resource not found" if booking ID doesn't exist (404 status)
        - Returns formatted booking details or error message
    """
    try:
        # Make API request
        booking = await _make_api_request(f"bookings/{params.booking_id}")

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            result = _format_markdown_booking(booking)
        else:
            result = json.dumps(booking, indent=2)

        return result

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_create_booking",
    annotations={
        "title": "Create Booking",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def beds24_create_booking(params: CreateBookingInput) -> str:
    """
    Create a new booking in Beds24.

    This tool creates a new reservation with guest information, dates, and preferences.
    The system will assign an available room unless a specific room is requested.

    Args:
        params (CreateBookingInput): Validated input parameters containing:
            - property_id (str): Property ID where booking will be created (required)
            - room_id (Optional[str]): Specific room ID to book (optional)
            - check_in (str): Check-in date (YYYY-MM-DD, required)
            - check_out (str): Check-out date (YYYY-MM-DD, required)
            - guest_name (str): Guest's full name (required)
            - guest_email (str): Guest's email address (required)
            - guest_phone (Optional[str]): Guest's phone number
            - number_of_guests (Optional[int]): Number of guests (default: 1)
            - special_requests (Optional[str]): Special requests or notes
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing created booking details with the following schema:

        Success response (JSON format):
        {
            "id": str,                    # New booking ID
            "status": str,                # Booking status (typically 'confirmed' or 'pending')
            "booking_reference": str,     # Booking reference number
            "check_in": str,              # Check-in date
            "check_out": str,             # Check-out date
            "guest_name": str,            # Guest name
            "property_id": str,           # Property ID
            "room_id": Optional[str],     # Assigned room ID
            "total_price": float,         # Calculated total price
            "message": str                # Success message
        }

        Error response:
        "Error: <error message>" (e.g., "Error: No rooms available for selected dates")

    Examples:
        - Use when: "Create a booking for John Doe at property 12345 from March 15-20"
        - Use when: "Reserve a room for 2 guests checking in tomorrow"
        - Don't use when: You want to modify an existing booking (use beds24_update_booking instead)

    Error Handling:
        - Returns "Error: No rooms available" if no rooms available for dates
        - Returns "Error: Invalid request" if dates are invalid or property doesn't exist
        - Returns formatted booking confirmation or error message
    """
    try:
        # Build booking data
        booking_data = {
            "propertyId": params.property_id,
            "checkIn": params.check_in,
            "checkOut": params.check_out,
            "guest": {
                "name": params.guest_name,
                "email": params.guest_email
            },
            "numberOfGuests": params.number_of_guests
        }

        if params.room_id:
            booking_data['roomId'] = params.room_id
        if params.guest_phone:
            booking_data['guest']['phone'] = params.guest_phone
        if params.special_requests:
            booking_data['specialRequests'] = params.special_requests

        # Make API request
        result = await _make_api_request("bookings", method="POST", json_data=booking_data)

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            booking_id = result.get('id', 'N/A')
            status = result.get('status', 'confirmed')
            total_price = result.get('totalPrice', 'N/A')

            lines = [
                f"## ✅ Booking Created Successfully",
                "",
                f"**Booking ID:** {booking_id}",
                f"**Status:** {status}",
                f"**Check-in:** {params.check_in}",
                f"**Check-out:** {params.check_out}",
                f"**Guest:** {params.guest_name}",
                f"**Property ID:** {params.property_id}",
                f"**Total Price:** {total_price}",
                "",
                "The booking has been created and confirmed in the system."
            ]
            result_str = "\n".join(lines)
        else:
            result['message'] = 'Booking created successfully'
            result_str = json.dumps(result, indent=2)

        return result_str

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_update_booking",
    annotations={
        "title": "Update Booking",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def beds24_update_booking(params: UpdateBookingInput) -> str:
    """
    Update an existing booking.

    This tool modifies booking details such as guest information, dates, or status.
    Only provided fields will be updated; unspecified fields remain unchanged.

    Args:
        params (UpdateBookingInput): Validated input parameters containing:
            - booking_id (str): The booking ID to update (required)
            - guest_name (Optional[str]): Updated guest name
            - guest_email (Optional[str]): Updated guest email
            - guest_phone (Optional[str]): Updated guest phone
            - number_of_guests (Optional[int]): Updated number of guests
            - check_in (Optional[str]): Updated check-in date (YYYY-MM-DD)
            - check_out (Optional[str]): Updated check-out date (YYYY-MM-DD)
            - special_requests (Optional[str]): Updated special requests
            - status (Optional[str]): Updated booking status
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing updated booking details with the following schema:

        Success response (JSON format):
        {
            "id": str,                    # Booking ID
            "status": str,                # Updated status
            "updated_fields": [str],      # List of fields that were updated
            "message": str                # Success message
        }

        Error response:
        "Error: Resource not found. Please check the booking ID is correct."

    Examples:
        - Use when: "Update guest email for booking BOOK-12345"
        - Use when: "Change check-out date for reservation 67890"
        - Use when: "Update special requests for booking"
        - Don't use when: You want to cancel a booking (use beds24_cancel_booking instead)

    Error Handling:
        - Returns "Error: Resource not found" if booking ID doesn't exist
        - Returns "Error: Invalid request" if update conflicts with existing bookings
        - Returns formatted update confirmation or error message
    """
    try:
        # Build update data (only include provided fields)
        update_data = {}

        if params.guest_name or params.guest_email or params.guest_phone:
            update_data['guest'] = {}
            if params.guest_name:
                update_data['guest']['name'] = params.guest_name
            if params.guest_email:
                update_data['guest']['email'] = params.guest_email
            if params.guest_phone:
                update_data['guest']['phone'] = params.guest_phone

        if params.number_of_guests is not None:
            update_data['numberOfGuests'] = params.number_of_guests
        if params.check_in:
            update_data['checkIn'] = params.check_in
        if params.check_out:
            update_data['checkOut'] = params.check_out
        if params.special_requests:
            update_data['specialRequests'] = params.special_requests
        if params.status:
            update_data['status'] = params.status

        # Make API request
        result = await _make_api_request(
            f"bookings/{params.booking_id}",
            method="POST",  # Beds24 uses POST for updates
            json_data=update_data
        )

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            booking_id = result.get('id', params.booking_id)
            status = result.get('status', 'updated')

            lines = [
                f"## ✅ Booking Updated Successfully",
                "",
                f"**Booking ID:** {booking_id}",
                f"**Status:** {status}",
                "",
                "The following fields were updated:",
                ""
            ]

            # List updated fields
            updated_fields = []
            if params.guest_name:
                updated_fields.append("Guest name")
            if params.guest_email:
                updated_fields.append("Guest email")
            if params.guest_phone:
                updated_fields.append("Guest phone")
            if params.number_of_guests is not None:
                updated_fields.append("Number of guests")
            if params.check_in:
                updated_fields.append("Check-in date")
            if params.check_out:
                updated_fields.append("Check-out date")
            if params.special_requests:
                updated_fields.append("Special requests")
            if params.status:
                updated_fields.append("Booking status")

            for field in updated_fields:
                lines.append(f"- ✅ {field}")

            if not updated_fields:
                lines.append("- No fields were updated (no changes provided)")

            result_str = "\n".join(lines)
        else:
            result['updated_fields'] = [
                k for k in ['guest_name', 'guest_email', 'guest_phone',
                           'number_of_guests', 'check_in', 'check_out',
                           'special_requests', 'status']
                if getattr(params, k) is not None
            ]
            result['message'] = 'Booking updated successfully'
            result_str = json.dumps(result, indent=2)

        return result_str

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_cancel_booking",
    annotations={
        "title": "Cancel Booking",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_cancel_booking(params: CancelBookingInput) -> str:
    """
    Cancel an existing booking.

    This tool cancels a booking and optionally records the cancellation reason.
    Cancellation may have financial implications depending on the booking's
    cancellation policy.

    Args:
        params (CancelBookingInput): Validated input parameters containing:
            - booking_id (str): The booking ID to cancel (required)
            - cancellation_reason (Optional[str]): Reason for cancellation
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response confirming cancellation with the following schema:

        Success response (JSON format):
        {
            "id": str,                    # Booking ID
            "status": "cancelled",        # New status
            "cancellation_reason": Optional[str],  # Reason provided
            "cancelled_at": str,          # Cancellation timestamp
            "refund_amount": Optional[float],      # Refund amount if applicable
            "message": str                # Confirmation message
        }

        Error response:
        "Error: Resource not found. Please check the booking ID is correct."
        or
        "Error: Cannot cancel booking - already checked in"

    Examples:
        - Use when: "Cancel booking BOOK-12345 due to guest request"
        - Use when: "Cancel reservation 67890 because of double booking"
        - Don't use when: You want to modify booking dates (use beds24_update_booking instead)

    Error Handling:
        - Returns "Error: Resource not found" if booking ID doesn't exist
        - Returns "Error: Cannot cancel booking" if booking is already checked in or completed
        - Returns formatted cancellation confirmation or error message
    """
    try:
        # Build cancellation data
        cancel_data = {}
        if params.cancellation_reason:
            cancel_data['cancellationReason'] = params.cancellation_reason

        # Make API request
        result = await _make_api_request(
            f"bookings/{params.booking_id}",
            method="DELETE",
            json_data=cancel_data if cancel_data else None
        )

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            booking_id = result.get('id', params.booking_id)
            refund_amount = result.get('refundAmount', 0)

            lines = [
                f"## ❌ Booking Cancelled Successfully",
                "",
                f"**Booking ID:** {booking_id}",
                f"**Status:** Cancelled",
                ""
            ]

            if params.cancellation_reason:
                lines.append(f"**Reason:** {params.cancellation_reason}")
                lines.append("")

            if refund_amount > 0:
                lines.append(f"💰 **Refund Amount:** {refund_amount}")
                lines.append("")

            lines.append("The booking has been cancelled and removed from the system.")

            result_str = "\n".join(lines)
        else:
            result['message'] = 'Booking cancelled successfully'
            result_str = json.dumps(result, indent=2)

        return result_str

    except Exception as e:
        return _handle_api_error(e)


# ==============================================================================
# Tool Implementations - Property Management
# ==============================================================================

@mcp.tool(
    name="beds24_list_properties",
    annotations={
        "title": "List Properties",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_list_properties(params: ListPropertiesInput) -> str:
    """
    List all properties managed in Beds24.

    This tool retrieves a list of properties with basic information.
    Supports pagination for accounts with many properties.

    Args:
        params (ListPropertiesInput): Validated input parameters containing:
            - limit (Optional[int]): Maximum results to return (default: 20, range: 1-100)
            - offset (Optional[int]): Pagination offset (default: 0)
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing property list with the following schema:

        Success response (JSON format):
        {
            "total": int,              # Total number of properties
            "count": int,              # Number of properties in this response
            "offset": int,             # Current pagination offset
            "has_more": bool,          # Whether more results are available
            "next_offset": Optional[int],  # Offset for next page
            "properties": [
                {
                    "id": str,         # Property ID
                    "name": str,       # Property name
                    "address": {
                        "city": str,   # City
                        "country": str # Country
                    },
                    "total_rooms": int # Number of rooms
                }
            ]
        }

        Error response:
        "Error: <error message>" or "No properties found"

    Examples:
        - Use when: "List all properties in the system"
        - Use when: "Show me available properties"
        - Don't use when: You need details of a specific property (use beds24_get_property instead)

    Error Handling:
        - Input validation errors are handled by Pydantic model
        - Returns "Error: Rate limit exceeded" if too many requests
        - Returns "No properties found" if no properties exist
    """
    try:
        # Build query parameters
        query_params = {
            'limit': params.limit,
            'offset': params.offset
        }

        # Make API request
        data = await _make_api_request("properties", params=query_params)

        properties = data.get('properties', [])
        total = data.get('total', len(properties))

        if not properties:
            return "No properties found"

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = ["# Property List", ""]
            lines.append(f"Total properties: {total} (showing {len(properties)} from offset {params.offset})")
            lines.append("")

            if total > params.limit + params.offset:
                lines.append(f"⚠️ More properties available. Use offset={params.offset + params.limit} to see next page.")
                lines.append("")

            for prop in properties:
                prop_id = prop.get('id', 'N/A')
                prop_name = prop.get('name', 'N/A')
                city = prop.get('address', {}).get('city', 'N/A')
                country = prop.get('address', {}).get('country', 'N/A')

                lines.append(f"## {prop_name} (ID: {prop_id})")
                lines.append(f"- **Location:** {city}, {country}")

                if 'totalRooms' in prop:
                    lines.append(f"- **Total Rooms:** {prop['totalRooms']}")

                lines.append("")

            result = "\n".join(lines)
        else:
            # JSON format
            response = {
                "total": total,
                "count": len(properties),
                "offset": params.offset,
                "has_more": total > params.offset + len(properties),
                "next_offset": params.offset + len(properties) if total > params.offset + len(properties) else None,
                "properties": properties
            }
            result = json.dumps(response, indent=2)

        # Check character limit
        if len(result) > CHARACTER_LIMIT:
            return (
                f"Response truncated. Found {total} properties but response exceeds {CHARACTER_LIMIT} character limit. "
                f"Use pagination (increase offset) to see properties in batches."
            )

        return result

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_get_property",
    annotations={
        "title": "Get Property Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_get_property(params: GetPropertyInput) -> str:
    """
    Get detailed information about a specific property.

    This tool retrieves complete property details including address, contact
    information, amenities, and configuration.

    Args:
        params (GetPropertyInput): Validated input parameters containing:
            - property_id (str): The property ID (required)
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing property details with the following schema:

        Success response (JSON format):
        {
            "id": str,                    # Property ID
            "name": str,                  # Property name
            "description": str,           # Property description
            "address": {
                "street": str,            # Street address
                "city": str,              # City
                "state": str,             # State/Province
                "postal_code": str,       # Postal code
                "country": str            # Country
            },
            "contact": {
                "email": str,             # Contact email
                "phone": str,             # Contact phone
                "website": Optional[str]  # Website URL
            },
            "amenities": [str],           # List of amenities
            "total_rooms": int,           # Total number of rooms
            "room_types": [               # Available room types
                {
                    "type": str,          # Room type (e.g., 'deluxe', 'standard')
                    "count": int          # Number of rooms of this type
                }
            ],
            "check_in_time": str,         # Standard check-in time
            "check_out_time": str,        # Standard check-out time
            "timezone": str               # Property timezone
        }

        Error response:
        "Error: Resource not found. Please check the property ID is correct."

    Examples:
        - Use when: "Get details for property 12345"
        - Use when: "Show me information about hotel PROP-67890"
        - Don't use when: You want to list multiple properties (use beds24_list_properties instead)

    Error Handling:
        - Returns "Error: Resource not found" if property ID doesn't exist
        - Returns formatted property details or error message
    """
    try:
        # Make API request
        property_data = await _make_api_request(f"properties/{params.property_id}")

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            result = _format_markdown_property(property_data)
        else:
            result = json.dumps(property_data, indent=2)

        return result

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_list_property_rooms",
    annotations={
        "title": "List Property Rooms",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_list_property_rooms(params: ListPropertyRoomsInput) -> str:
    """
    List all rooms for a specific property.

    This tool retrieves detailed information about rooms in a property,
    including room types, capacities, amenities, and current status.

    Args:
        params (ListPropertyRoomsInput): Validated input parameters containing:
            - property_id (str): The property ID to get rooms for (required)
            - room_type (Optional[str]): Filter by specific room type
            - limit (Optional[int]): Maximum results to return (default: 50, range: 1-100)
            - offset (Optional[int]): Pagination offset (default: 0)
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing room list with the following schema:

        Success response (JSON format):
        {
            "property_id": str,           # Property ID
            "property_name": str,         # Property name
            "total": int,                 # Total number of rooms
            "count": int,                 # Number of rooms in this response
            "offset": int,                # Current pagination offset
            "has_more": bool,             # Whether more results are available
            "rooms": [
                {
                    "id": str,            # Room ID
                    "name": str,          # Room name
                    "type": str,          # Room type (e.g., 'deluxe', 'standard')
                    "capacity": int,      # Maximum occupancy
                    "amenities": [str],   # Room amenities
                    "price": float,       # Base price per night
                    "status": str,        # Current status (e.g., 'available', 'occupied')
                    "floor": Optional[int] # Floor number
                }
            ]
        }

        Error response:
        "Error: Resource not found. Please check the property ID is correct."

    Examples:
        - Use when: "List all rooms in property 12345"
        - Use when: "Show me deluxe rooms available at hotel PROP-67890"
        - Don't use when: You need property-level information (use beds24_get_property instead)

    Error Handling:
        - Returns "Error: Resource not found" if property ID doesn't exist
        - Returns formatted room list or error message
    """
    try:
        # Build query parameters
        query_params = {
            'limit': params.limit,
            'offset': params.offset
        }
        if params.room_type:
            query_params['roomType'] = params.room_type

        # Make API request
        data = await _make_api_request(
            f"properties/{params.property_id}/rooms",
            params=query_params
        )

        rooms = data.get('rooms', [])
        total = data.get('total', len(rooms))
        property_name = data.get('propertyName', 'Unknown Property')

        if not rooms:
            return f"No rooms found for property {params.property_id}"

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [f"# Rooms at {property_name} (ID: {params.property_id})", ""]
            lines.append(f"Total rooms: {total} (showing {len(rooms)} from offset {params.offset})")
            lines.append("")

            if total > params.limit + params.offset:
                lines.append(f"⚠️ More rooms available. Use offset={params.offset + params.limit} to see next page.")
                lines.append("")

            for room in rooms:
                lines.append(_format_markdown_room(room))

            result = "\n".join(lines)
        else:
            # JSON format
            response = {
                "property_id": params.property_id,
                "property_name": property_name,
                "total": total,
                "count": len(rooms),
                "offset": params.offset,
                "has_more": total > params.offset + len(rooms),
                "next_offset": params.offset + len(rooms) if total > params.offset + len(rooms) else None,
                "rooms": rooms
            }
            result = json.dumps(response, indent=2)

        # Check character limit
        if len(result) > CHARACTER_LIMIT:
            return (
                f"Response truncated. Found {total} rooms but response exceeds {CHARACTER_LIMIT} character limit. "
                f"Use room_type filter or pagination to see fewer rooms."
            )

        return result

    except Exception as e:
        return _handle_api_error(e)


# ==============================================================================
# Tool Implementations - Inventory & Pricing
# ==============================================================================

@mcp.tool(
    name="beds24_check_availability",
    annotations={
        "title": "Check Room Availability",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_check_availability(params: CheckAvailabilityInput) -> str:
    """
    Check room availability for specific dates.

    This tool checks if rooms are available for the requested date range and
    returns available room options with pricing information.

    Args:
        params (CheckAvailabilityInput): Validated input parameters containing:
            - property_id (str): The property ID to check (required)
            - check_in (str): Check-in date (YYYY-MM-DD, required)
            - check_out (str): Check-out date (YYYY-MM-DD, required)
            - room_type (Optional[str]): Specific room type to check
            - number_of_guests (Optional[int]): Number of guests (default: 1)
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing availability information with the following schema:

        Success response (JSON format):
        {
            "property_id": str,           # Property ID
            "check_in": str,              # Check-in date
            "check_out": str,             # Check-out date
            "available": bool,            # Overall availability
            "available_rooms": [          # List of available rooms
                {
                    "id": str,            # Room ID
                    "name": str,          # Room name
                    "type": str,          # Room type
                    "capacity": int,      # Maximum occupancy
                    "price_per_night": float,  # Price per night
                    "total_price": float  # Total price for stay
                }
            ],
            "price_range": {              # Price range for available rooms
                "min": float,             # Minimum price per night
                "max": float              # Maximum price per night
            },
            "nights": int                 # Number of nights
        }

        Error response:
        "Error: Resource not found. Please check the property ID is correct."
        or
        "❌ No rooms available for the requested dates."

    Examples:
        - Use when: "Check availability at property 12345 for March 15-20"
        - Use when: "Are there any deluxe rooms available next week?"
        - Don't use when: You want to see the full calendar (use beds24_get_calendar instead)

    Error Handling:
        - Returns "Error: Resource not found" if property ID doesn't exist
        - Returns "No rooms available" if no rooms match criteria
        - Returns formatted availability information or error message
    """
    try:
        # Build query parameters
        query_params = {
            'checkIn': params.check_in,
            'checkOut': params.check_out,
            'numberOfGuests': params.number_of_guests
        }
        if params.room_type:
            query_params['roomType'] = params.room_type

        # Make API request
        availability = await _make_api_request(
            f"inventory/rooms/availability/{params.property_id}",
            params=query_params
        )

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            result = _format_markdown_availability(availability)
        else:
            result = json.dumps(availability, indent=2)

        return result

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_get_calendar",
    annotations={
        "title": "Get Room Calendar",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_get_calendar(params: GetCalendarInput) -> str:
    """
    Get calendar values for rooms over a date range.

    This tool retrieves detailed calendar information including prices,
    availability status, and booking restrictions for specific dates.

    Args:
        params (GetCalendarInput): Validated input parameters containing:
            - property_id (str): The property ID (required)
            - room_id (Optional[str]): Specific room ID (if not provided, returns all rooms)
            - start_date (str): Start date for calendar (YYYY-MM-DD, required)
            - end_date (str): End date for calendar (YYYY-MM-DD, required)
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing calendar data with the following schema:

        Success response (JSON format):
        {
            "property_id": str,           # Property ID
            "room_id": Optional[str],     # Room ID (if specified)
            "start_date": str,            # Calendar start date
            "end_date": str,              # Calendar end date
            "dates": [
                {
                    "date": str,          # Date (YYYY-MM-DD)
                    "available": bool,    # Availability status
                    "price": float,       # Price for the date
                    "minimum_stay": Optional[int],  # Minimum stay requirement
                    "maximum_stay": Optional[int],  # Maximum stay limit
                    "bookings": [         # Bookings on this date
                        {
                            "id": str,    # Booking ID
                            "guest_name": str  # Guest name
                        }
                    ]
                }
            ]
        }

        Error response:
        "Error: Resource not found. Please check the property ID is correct."

    Examples:
        - Use when: "Get calendar for property 12345 from March 1-31"
        - Use when: "Show me pricing and availability for room ROOM-123 in April"
        - Don't use when: You just want to check if rooms are available (use beds24_check_availability instead)

    Error Handling:
        - Returns "Error: Resource not found" if property or room ID doesn't exist
        - Returns formatted calendar data or error message
    """
    try:
        # Build endpoint
        endpoint = f"inventory/rooms/calendar/{params.property_id}"
        if params.room_id:
            endpoint = f"inventory/rooms/calendar/{params.property_id}/{params.room_id}"

        # Build query parameters
        query_params = {
            'startDate': params.start_date,
            'endDate': params.end_date
        }

        # Make API request
        calendar_data = await _make_api_request(endpoint, params=query_params)

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            result = _format_markdown_calendar(calendar_data)
        else:
            result = json.dumps(calendar_data, indent=2)

        # Check character limit
        if len(result) > CHARACTER_LIMIT:
            # Truncate dates array
            if 'dates' in calendar_data:
                original_count = len(calendar_data['dates'])
                max_dates = max(1, CHARACTER_LIMIT // 500)  # Approx 500 chars per date
                calendar_data['dates'] = calendar_data['dates'][:max_dates]
                calendar_data['truncated'] = True
                calendar_data['original_count'] = original_count
                calendar_data['displayed_count'] = max_dates
                result = json.dumps(calendar_data, indent=2)
                result += f"\n\n⚠️ Response truncated from {original_count} to {max_dates} dates due to character limit."

        return result

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_update_calendar",
    annotations={
        "title": "Update Room Calendar",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def beds24_update_calendar(params: UpdateCalendarInput) -> str:
    """
    Update calendar values for a specific date.

    This tool modifies calendar information including price, availability,
    and stay restrictions for a specific date and room.

    Args:
        params (UpdateCalendarInput): Validated input parameters containing:
            - property_id (str): The property ID (required)
            - room_id (Optional[str]): Specific room ID to update
            - date (str): Date to update (YYYY-MM-DD, required)
            - price (Optional[float]): Updated price for the date
            - availability (Optional[bool]): Availability status (true/false)
            - minimum_stay (Optional[int]): Minimum stay requirement in nights
            - maximum_stay (Optional[int]): Maximum stay limit in nights
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response confirming the update with the following schema:

        Success response (JSON format):
        {
            "property_id": str,           # Property ID
            "room_id": Optional[str],     # Room ID (if specified)
            "date": str,                  # Updated date
            "updated_fields": {           # Fields that were updated
                "price": Optional[float],
                "available": Optional[bool],
                "minimum_stay": Optional[int],
                "maximum_stay": Optional[int]
            },
            "message": str                # Confirmation message
        }

        Error response:
        "Error: Resource not found. Please check the property ID is correct."
        or
        "Error: Invalid request - No update values provided"

    Examples:
        - Use when: "Update price for room ROOM-123 on March 15 to $199.99"
        - Use when: "Mark March 20 as unavailable for maintenance"
        - Use when: "Set minimum stay to 3 nights for holiday period"
        - Don't use when: You want to view calendar data (use beds24_get_calendar instead)

    Error Handling:
        - Returns "Error: Resource not found" if property or room ID doesn't exist
        - Returns "Error: Invalid request" if no update values provided
        - Returns formatted update confirmation or error message
    """
    try:
        # Validate that at least one update field is provided
        if params.price is None and params.availability is None \
           and params.minimum_stay is None and params.maximum_stay is None:
            return "Error: Invalid request - No update values provided. Please specify at least one field to update (price, availability, minimum_stay, or maximum_stay)."

        # Build update data
        update_data = {
            'date': params.date
        }

        if params.price is not None:
            update_data['price'] = params.price
        if params.availability is not None:
            update_data['available'] = params.availability
        if params.minimum_stay is not None:
            update_data['minimumStay'] = params.minimum_stay
        if params.maximum_stay is not None:
            update_data['maximumStay'] = params.maximum_stay

        # Build endpoint
        endpoint = f"inventory/rooms/calendar/{params.property_id}"
        if params.room_id:
            endpoint = f"inventory/rooms/calendar/{params.property_id}/{params.room_id}"

        # Make API request
        result = await _make_api_request(endpoint, method="POST", json_data=update_data)

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [
                f"## ✅ Calendar Updated Successfully",
                "",
                f"**Property ID:** {params.property_id}",
                f"**Date:** {params.date}",
                ""
            ]

            if params.room_id:
                lines.append(f"**Room ID:** {params.room_id}")
                lines.append("")

            lines.append("The following fields were updated:")
            lines.append("")

            if params.price is not None:
                lines.append(f"- ✅ **Price:** ${params.price}")
            if params.availability is not None:
                status = "Available" if params.availability else "Not Available"
                lines.append(f"- ✅ **Availability:** {status}")
            if params.minimum_stay is not None:
                lines.append(f"- ✅ **Minimum Stay:** {params.minimum_stay} nights")
            if params.maximum_stay is not None:
                lines.append(f"- ✅ **Maximum Stay:** {params.maximum_stay} nights")

            result_str = "\n".join(lines)
        else:
            updated_fields = {}
            if params.price is not None:
                updated_fields['price'] = params.price
            if params.availability is not None:
                updated_fields['available'] = params.availability
            if params.minimum_stay is not None:
                updated_fields['minimum_stay'] = params.minimum_stay
            if params.maximum_stay is not None:
                updated_fields['maximum_stay'] = params.maximum_stay

            response = {
                "property_id": params.property_id,
                "room_id": params.room_id,
                "date": params.date,
                "updated_fields": updated_fields,
                "message": "Calendar updated successfully"
            }
            result_str = json.dumps(response, indent=2)

        return result_str

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_get_pricing_offers",
    annotations={
        "title": "Get Pricing Offers",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_get_pricing_offers(params: GetPricingOffersInput) -> str:
    """
    Get pricing offers for a date range.

    This tool retrieves available pricing options and special offers for the
    requested date range, including any discounts or promotions.

    Args:
        params (GetPricingOffersInput): Validated input parameters containing:
            - property_id (str): The property ID (required)
            - check_in (str): Check-in date (YYYY-MM-DD, required)
            - check_out (str): Check-out date (YYYY-MM-DD, required)
            - number_of_guests (Optional[int]): Number of guests (default: 1)
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing pricing offers with the following schema:

        Success response (JSON format):
        {
            "property_id": str,           # Property ID
            "check_in": str,              # Check-in date
            "check_out": str,             # Check-out date
            "nights": int,                # Number of nights
            "offers": [
                {
                    "room_type": str,     # Room type
                    "room_name": str,     # Room name
                    "base_price": float,  # Base price per night
                    "total_price": float, # Total price for stay
                    "discount": Optional[float],   # Discount amount
                    "discount_percent": Optional[float],  # Discount percentage
                    "offer_name": Optional[str],   # Name of special offer
                    "offer_description": Optional[str],  # Offer description
                    "available": bool     # Whether this offer is available
                }
            ],
            "best_offer": {               # Best available offer
                "room_type": str,
                "total_price": float,
                "savings": float          # Savings compared to base price
            }
        }

        Error response:
        "Error: Resource not found. Please check the property ID is correct."

    Examples:
        - Use when: "Get pricing offers for property 12345 from March 15-20"
        - Use when: "What are the best rates available for a 3-night stay?"
        - Don't use when: You need detailed availability (use beds24_check_availability instead)

    Error Handling:
        - Returns "Error: Resource not found" if property ID doesn't exist
        - Returns formatted pricing offers or error message
    """
    try:
        # Build query parameters
        query_params = {
            'checkIn': params.check_in,
            'checkOut': params.check_out,
            'numberOfGuests': params.number_of_guests
        }

        # Make API request
        offers = await _make_api_request(
            f"inventory/rooms/offers/{params.property_id}",
            params=query_params
        )

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [
                f"# Pricing Offers for Property {params.property_id}",
                "",
                f"**Dates:** {params.check_in} to {params.check_out}",
                f"**Nights:** {offers.get('nights', 0)}",
                ""
            ]

            if 'offers' in offers and offers['offers']:
                lines.append("## Available Offers")
                lines.append("")

                for offer in offers['offers']:
                    if offer.get('available', False):
                        room_name = offer.get('room_name', 'Unknown Room')
                        room_type = offer.get('room_type', 'Unknown Type')
                        total_price = offer.get('total_price', 0)
                        base_price = offer.get('base_price', 0)
                        discount = offer.get('discount', 0)

                        lines.append(f"### {room_name} ({room_type})")
                        lines.append(f"- **Total Price:** ${total_price}")
                        lines.append(f"- **Base Price:** ${base_price}")

                        if discount > 0:
                            discount_pct = offer.get('discount_percent', 0)
                            lines.append(f"- **🎉 Discount:** ${discount} ({discount_pct}%)")

                        if 'offer_name' in offer:
                            lines.append(f"- **Offer:** {offer['offer_name']}")

                        if 'offer_description' in offer:
                            lines.append(f"- **Description:** {offer['offer_description']}")

                        lines.append("")
            else:
                lines.append("❌ No pricing offers available for the requested dates.")

            if 'best_offer' in offers:
                lines.append("## 💰 Best Offer")
                lines.append("")
                best = offers['best_offer']
                lines.append(f"- **Room Type:** {best.get('room_type', 'N/A')}")
                lines.append(f"- **Total Price:** ${best.get('total_price', 0)}")
                lines.append(f"- **Savings:** ${best.get('savings', 0)}")
                lines.append("")

            result = "\n".join(lines)
        else:
            result = json.dumps(offers, indent=2)

        return result

    except Exception as e:
        return _handle_api_error(e)


# ==============================================================================
# Main Entry Point
# ==============================================================================

if __name__ == "__main__":
    # Run the MCP server
    # Default: stdio transport for local development
    # Use --transport streamable-http --port 8000 for HTTP server
    mcp.run()
