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
from fastmcp import FastMCP, Context

# Initialize MCP server
mcp = FastMCP("beds24_mcp")

# ==============================================================================
# Constants and Configuration
# ==============================================================================

API_BASE_URL = os.getenv("BEDS24_API_BASE_URL", "https://api.beds24.com/v2")
REFRESH_TOKEN = os.getenv("BEDS24_REFRESH_TOKEN", "")
CHARACTER_LIMIT = 100000  # Maximum response size in characters

# ==============================================================================
# Token Manager - Auto-refresh access token from refresh token
# ==============================================================================

class TokenManager:
    """Manages access token with auto-refresh from refresh token."""

    def __init__(self, refresh_token: str):
        self._refresh_token = refresh_token
        self._access_token: Optional[str] = None
        self._expires_at: float = 0  # Unix timestamp

    async def get_access_token(self) -> str:
        """Get valid access token, refreshing if needed."""
        import time

        # Return cached token if still valid (with 5 min buffer)
        if self._access_token and time.time() < (self._expires_at - 300):
            return self._access_token

        # Need to refresh
        if not self._refresh_token:
            raise ValueError(
                "BEDS24_REFRESH_TOKEN not set. "
                "Run beds24_setup_refresh_token with an invite code first."
            )

        # Get new access token from refresh token
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/authentication/token",
                headers={"refreshToken": self._refresh_token},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

        self._access_token = data.get("token")
        expires_in = data.get("expiresIn", 3600)
        self._expires_at = time.time() + expires_in

        return self._access_token

    def update_refresh_token(self, new_refresh_token: str):
        """Update refresh token (from invite code setup)."""
        self._refresh_token = new_refresh_token
        self._access_token = None  # Force refresh on next request
        self._expires_at = 0


# Global token manager instance
_token_manager = TokenManager(REFRESH_TOKEN)

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

    Automatically gets/refreshes access token from refresh token.

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
    # Get access token (auto-refresh if needed)
    access_token = await _token_manager.get_access_token()

    headers = {
        "token": access_token,
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
        # Handle empty response bodies (e.g. 204 No Content)
        if not response.content or response.status_code == 204:
            return {}
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
        description="Filter by booking status (e.g., 'confirmed', 'pending', 'cancelled', 'inquiry')",
        min_length=1,
        max_length=50
    )
    arrival: Optional[str] = Field(
        default=None,
        description="Filter by arrival/check-in date (format: YYYY-MM-DD, e.g., '2026-03-18')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    arrival_from: Optional[str] = Field(
        default=None,
        description="Filter by arrival date from (format: YYYY-MM-DD, e.g., '2026-03-18')",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        alias="arrivalFrom"
    )
    arrival_to: Optional[str] = Field(
        default=None,
        description="Filter by arrival date to (format: YYYY-MM-DD, e.g., '2026-03-20')",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        alias="arrivalTo"
    )
    departure: Optional[str] = Field(
        default=None,
        description="Filter by departure/check-out date (format: YYYY-MM-DD, e.g., '2026-03-20')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    departure_from: Optional[str] = Field(
        default=None,
        description="Filter by departure date from (format: YYYY-MM-DD, e.g., '2026-03-20')",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        alias="departureFrom"
    )
    departure_to: Optional[str] = Field(
        default=None,
        description="Filter by departure date to (format: YYYY-MM-DD, e.g., '2026-03-25')",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        alias="departureTo"
    )
    limit: Optional[int] = Field(
        default=20,
        description="Maximum number of bookings to return (range: 1-300)",
        ge=1,
        le=300
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
    include_invoice_items: Optional[bool] = Field(
        default=True,
        description="Include invoice items in response (default: true)"
    )
    include_info_items: Optional[bool] = Field(
        default=False,
        description="Include info items in response (default: false, set true for extra info fields)"
    )
    include_booking_group: Optional[bool] = Field(
        default=True,
        description="Include booking group data in response (default: true)"
    )
    compact: Optional[bool] = Field(
        default=True,
        description="Return compact response with essential fields only (id, status, arrival, departure, propertyId, unitId, totalPrice, currency, invoiceItems, bookingGroup). Default: true. Set false only when full raw booking data is needed."
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


class GetBookingsByMasterInput(BaseModel):
    """Input model for getting all bookings in a group by master ID."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    master_id: str = Field(
        ...,
        description="The master booking ID to get all related bookings in the group",
        min_length=1,
        max_length=100
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class InvoiceItemInput(BaseModel):
    """Single invoice item (charge or payment) to attach to a booking."""
    model_config = ConfigDict(extra='forbid')

    type: str = Field(
        ...,
        description="Item type: 'charge' or 'payment'",
    )
    sub_type: Optional[int] = Field(
        default=None,
        description="Sub-type code (e.g., 8 for Cancel Fee, 200 for Cash payment)",
        alias="subType"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the item",
        max_length=200
    )
    qty: Optional[int] = Field(
        default=1,
        description="Quantity (for charge items)",
        ge=1
    )
    amount: float = Field(
        ...,
        description="Unit amount (positive for charges, can be negative for payments)"
    )

    model_config = ConfigDict(populate_by_name=True)


class InvoiceItemUpdateInput(BaseModel):
    """Invoice item for update or create — omit id to create a new item, include id to update existing."""
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    id: Optional[int] = Field(default=None, description="Invoice item ID — omit to create new, provide to update existing")
    type: Optional[str] = Field(default=None, description="Item type: 'charge' or 'payment' (required when creating new item)")
    description: Optional[str] = Field(default=None, description="Item description (e.g. '[ROOMNAME1]*')")
    qty: Optional[int] = Field(default=None, description="Quantity", ge=1)
    amount: Optional[float] = Field(default=None, description="Unit amount")
    line_total: Optional[float] = Field(default=None, description="Line total", alias="lineTotal")


class CreateBookingInput(BaseModel):
    """Input model for creating a new booking."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    room_id: int = Field(
        ...,
        description="Beds24 room ID to book (e.g., 1234567)",
    )
    status: Optional[str] = Field(
        default="confirmed",
        description="Booking status: 'confirmed', 'provisional', 'cancelled', etc.",
    )
    arrival: str = Field(
        ...,
        description="Arrival (check-in) date (format: YYYY-MM-DD, e.g., '2024-03-15')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    departure: str = Field(
        ...,
        description="Departure (check-out) date (format: YYYY-MM-DD, e.g., '2024-03-20')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    num_adult: Optional[int] = Field(
        default=1,
        description="Number of adults (must be >= 1)",
        ge=1
    )
    num_child: Optional[int] = Field(
        default=0,
        description="Number of children (must be >= 0)",
        ge=0
    )
    title: Optional[str] = Field(
        default=None,
        description="Guest title (e.g., 'Mr', 'Mrs', 'Ms', 'Dr')",
        max_length=20
    )
    first_name: str = Field(
        ...,
        description="Guest's first name (e.g., 'John')",
        min_length=1,
        max_length=100
    )
    last_name: str = Field(
        ...,
        description="Guest's last name / surname (e.g., 'Doe')",
        min_length=1,
        max_length=100
    )
    email: str = Field(
        ...,
        description="Guest's email address (e.g., 'john@example.com')",
        pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$'
    )
    phone: Optional[str] = Field(
        default=None,
        description="Guest's phone number (e.g., '+49 176 39637463')",
        max_length=50
    )
    address: Optional[str] = Field(
        default=None,
        description="Guest's street address",
        max_length=200
    )
    city: Optional[str] = Field(
        default=None,
        description="Guest's city",
        max_length=100
    )
    state: Optional[str] = Field(
        default=None,
        description="Guest's state/province",
        max_length=100
    )
    postcode: Optional[str] = Field(
        default=None,
        description="Guest's postcode/zip code",
        max_length=20
    )
    country: Optional[str] = Field(
        default=None,
        description="Guest's country (e.g., 'Australia', 'Vietnam')",
        max_length=100
    )
    channel: Optional[str] = Field(
        default=None,
        description="Booking channel (e.g., 'booking', 'airbnb', 'direct')",
        max_length=50
    )
    unit_id: Optional[int] = Field(
        default=None,
        description="Specific unit ID within the room (for multi-unit rooms)"
    )
    price: Optional[float] = Field(
        default=None,
        description="Total booking price override"
    )
    commission: Optional[float] = Field(
        default=None,
        description="Commission amount"
    )
    invoice_items: Optional[List[InvoiceItemInput]] = Field(
        default=None,
        description="Invoice items (charges and payments) to attach to the booking"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )

    @field_validator('departure')
    @classmethod
    def validate_dates(cls, v: str, info) -> str:
        """Validate that departure is after arrival."""
        arrival = info.data.get('arrival')
        if arrival and v:
            if v <= arrival:
                raise ValueError("Departure date must be after arrival date")
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
    invoice_items: Optional[List[InvoiceItemUpdateInput]] = Field(
        default=None,
        description="Invoice items to update — each item requires id, and optionally qty and/or amount"
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


class DeleteBookingInput(BaseModel):
    """Input model for deleting a booking."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    booking_id: str = Field(
        ...,
        description="The booking ID to delete permanently (e.g., 'BOOK-12345')",
        min_length=1,
        max_length=100
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
        description="The property ID to check availability for (e.g., '322626')",
        min_length=1,
        max_length=100
    )
    room_id: Optional[int] = Field(
        default=None,
        description="Specific room ID to check (e.g., 124124). If not provided, checks all rooms.",
    )
    start_date: str = Field(
        ...,
        description="Start date of stay (format: YYYY-MM-DD, e.g., '2026-06-15')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end_date: str = Field(
        ...,
        description="End date of stay (format: YYYY-MM-DD, e.g., '2026-06-20')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )

    @field_validator('end_date')
    @classmethod
    def validate_dates(cls, v: str, info) -> str:
        """Validate that end_date is after start_date."""
        start_date = info.data.get('start_date')
        if start_date and v:
            if v <= start_date:
                raise ValueError("End date must be after start date")
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
        description="The property ID (e.g., '151551')",
        min_length=1,
        max_length=100
    )
    room_id: Optional[int] = Field(
        default=None,
        description="Specific room ID (e.g., 1515151). If not provided, returns all rooms.",
    )
    start_date: str = Field(
        ...,
        description="Start date for calendar (format: YYYY-MM-DD, e.g., '2025-03-01')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end_date: str = Field(
        ...,
        description="End date for calendar (format: YYYY-MM-DD, e.g., '2025-03-31')",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    # Include flags — all default True for full calendar data
    include_num_avail: bool = Field(default=True, description="Include number of available units")
    include_min_stay: bool = Field(default=True, description="Include minimum stay restrictions")
    include_max_stay: bool = Field(default=True, description="Include maximum stay restrictions")
    include_multiplier: bool = Field(default=True, description="Include price multipliers")
    include_override: bool = Field(default=True, description="Include price overrides")
    include_prices: bool = Field(default=True, description="Include base prices")
    include_linked_prices: bool = Field(default=True, description="Include linked/derived prices")
    include_channels: bool = Field(default=True, description="Include channel-specific data")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class CalendarRangeInput(BaseModel):
    """A single date-range entry in a calendar update."""
    model_config = ConfigDict(extra='forbid', populate_by_name=True)

    from_date: str = Field(
        ...,
        alias="from",
        description="Start date of the range (YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    to_date: str = Field(
        ...,
        alias="to",
        description="End date of the range (YYYY-MM-DD, inclusive)",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    price1: Optional[float] = Field(default=None, description="Primary price (e.g., base rate)", ge=0)
    price2: Optional[float] = Field(default=None, description="Secondary price (e.g., extra guest rate)", ge=0)
    min_stay: Optional[int] = Field(default=None, description="Minimum stay in nights", ge=1)
    max_stay: Optional[int] = Field(default=None, description="Maximum stay in nights", ge=1)
    num_avail: Optional[int] = Field(default=None, description="Number of available units", ge=0)
    override: Optional[str] = Field(default=None, description="Override type (e.g., 'blackout')")
    channels: Optional[Dict[str, Any]] = Field(
        default=None,
        description='Channel-specific settings, e.g. {"airbnb": {"maxBookings": 4}}'
    )


class RoomCalendarUpdate(BaseModel):
    """Calendar updates for a single room."""
    model_config = ConfigDict(extra='forbid')

    room_id: int = Field(..., description="Beds24 room ID to update")
    calendar: List[CalendarRangeInput] = Field(..., description="List of date-range update entries")


class UpdateCalendarInput(BaseModel):
    """Input model for updating calendar values (batch: multiple rooms × date ranges)."""
    model_config = ConfigDict(extra='forbid')

    rooms: List[RoomCalendarUpdate] = Field(
        ...,
        description="List of room calendar updates. Each entry has a roomId and calendar array."
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
    if any(k in booking for k in ['firstName', 'lastName', 'email', 'guest', 'guestName']):
        lines.append("### Guest Information")
        # API returns firstName/lastName directly
        first_name = booking.get('firstName', '')
        last_name = booking.get('lastName', '')
        guest_name = f"{first_name} {last_name}".strip() or booking.get('guestName') or 'N/A'
        guest_email = booking.get('email') or booking.get('guestEmail') or booking.get('guest', {}).get('email', 'N/A')
        guest_phone = booking.get('phone') or booking.get('guestPhone') or booking.get('guest', {}).get('phone', '')

        lines.append(f"- **Name:** {guest_name}")
        lines.append(f"- **Email:** {guest_email}")
        if guest_phone:
            lines.append(f"- **Phone:** {guest_phone}")
        lines.append("")

    # Property & Room
    if 'propertyId' in booking or 'roomId' in booking:
        lines.append("### Property & Room")
        property_id = booking.get('propertyId', 'N/A')
        room_id = booking.get('roomId', 'N/A')

        lines.append(f"- **Property ID:** {property_id}")
        lines.append(f"- **Room ID:** {room_id}")
        lines.append("")

    # Invoice Items
    invoice_items = booking.get('invoiceItems', [])
    if invoice_items:
        lines.append("### Invoice Items")
        for item in invoice_items:
            item_type = item.get('type', 'N/A')
            desc = item.get('description', 'N/A')
            amount = item.get('amount', 0)
            qty = item.get('qty', 1)
            line_total = item.get('lineTotal', amount)
            lines.append(f"- **{item_type}**: {desc} - {amount:,.0f} x {qty} = {line_total:,.0f}")
        lines.append("")

    # Info Items
    info_items = booking.get('infoItems', [])
    if info_items:
        lines.append("### Info Items")
        for item in info_items:
            desc = item.get('description', 'N/A')
            lines.append(f"- {desc}")
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
        # Build query parameters - Beds24 API uses 'arrival' and 'departure'
        query_params = {}
        if params.property_id:
            query_params['propertyId'] = params.property_id
        if params.status:
            query_params['status'] = params.status
        if params.arrival:
            query_params['arrival'] = params.arrival
        if params.arrival_from:
            query_params['arrivalFrom'] = params.arrival_from
        if params.arrival_to:
            query_params['arrivalTo'] = params.arrival_to
        if params.departure:
            query_params['departure'] = params.departure
        if params.departure_from:
            query_params['departureFrom'] = params.departure_from
        if params.departure_to:
            query_params['departureTo'] = params.departure_to
        if params.limit:
            query_params['limit'] = params.limit
        if params.offset:
            query_params['offset'] = params.offset

        # Include related data
        if params.include_invoice_items:
            query_params['includeInvoiceItems'] = 'true'
        if params.include_info_items:
            query_params['includeInfoItems'] = 'true'
        if params.include_booking_group:
            query_params['includeBookingGroup'] = 'true'

        # Fetch bookings using API-level pagination
        # Beds24 API uses 1-indexed page numbers, 100 records/page
        # Convert offset to start page + in-page skip to avoid re-fetching from page 1
        offset = params.offset or 0
        limit = params.limit or 20
        PAGE_SIZE = 100

        start_page = (offset // PAGE_SIZE) + 1
        skip_in_page = offset % PAGE_SIZE

        # Cap limit to 300 to avoid excessive API calls (3 pages × 100 records)
        limit = min(limit, 300)

        all_bookings = []
        page = start_page
        max_pages = start_page + 2  # Allow up to 3 API calls from start page (~90s max)
        api_has_more = False
        api_total = None

        while len(all_bookings) < (skip_in_page + limit) and page <= max_pages:
            query_params['page'] = page
            query_params['limit'] = PAGE_SIZE

            data = await _make_api_request("bookings", params=query_params)

            bookings_page = data.get('data', []) if isinstance(data, dict) else []
            if not bookings_page:
                break

            all_bookings.extend(bookings_page)

            api_has_more = data.get('pages', {}).get('nextPageExists', False)
            api_total = data.get('count')

            if not api_has_more:
                break

            page += 1

        # Slice: skip in-page offset, then take limit
        bookings = all_bookings[skip_in_page:skip_in_page + limit]
        total_fetched = len(all_bookings)
        remaining_after_slice = total_fetched > skip_in_page + len(bookings)
        has_more = api_has_more or remaining_after_slice

        if not bookings:
            return "No bookings found matching criteria"

        # Beds24 API 'count' = records on current page, NOT global total.
        # Total is only accurate when we've reached the last page (has_more=False).
        if not has_more:
            total_count = offset + len(all_bookings)  # offset before + all we fetched = exact total
        else:
            total_count = None  # Unknown — more pages exist

        # Apply compact mode: strip to essential fields only
        COMPACT_FIELDS = {"id", "status", "arrival", "departure", "propertyId",
                          "unitId", "totalPrice", "currency",
                          "invoiceItems", "bookingGroup"}
        if params.compact:
            bookings = [{k: v for k, v in b.items() if k in COMPACT_FIELDS} for b in bookings]

        # Format response
        total_label = str(total_count) if total_count is not None else "unknown (more pages exist)"
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = ["# Booking List", ""]
            lines.append(f"Total bookings: {total_label} (showing {len(bookings)} from offset {offset})")
            lines.append("")

            if has_more:
                lines.append(f"⚠️ More bookings available. Use offset={offset + len(bookings)} to see next page.")
                lines.append("")

            for booking in bookings:
                lines.append(_format_markdown_booking(booking))

            result = "\n".join(lines)
        else:
            # JSON format
            response = {
                "total": total_count,       # null when has_more=true (unknown), exact count when has_more=false
                "count": len(bookings),
                "offset": offset,
                "has_more": has_more,
                "next_offset": offset + len(bookings) if has_more else None,
                "bookings": bookings
            }
            result = json.dumps(response, indent=2)

        # Check character limit - if exceeded, truncate and return partial data
        if len(result) > CHARACTER_LIMIT:
            # Calculate how many bookings we can include
            result_length = len(result)
            bookings_count = len(bookings)
            avg_chars_per_booking = result_length // max(1, bookings_count)

            # Estimate safe count (leave 10% margin for JSON overhead)
            safe_count = max(1, int((CHARACTER_LIMIT * 0.9) / avg_chars_per_booking))

            # Truncate bookings
            truncated_bookings = bookings[:safe_count]

            if params.response_format == ResponseFormat.MARKDOWN:
                lines = ["# Booking List", ""]
                lines.append(f"Total bookings: {total_count} (showing {len(truncated_bookings)} of {bookings_count} from offset {offset})")
                lines.append("")
                lines.append(f"⚠️ Response truncated due to size limit. Use offset={offset + len(truncated_bookings)} to see next batch.")
                lines.append("")

                for booking in truncated_bookings:
                    lines.append(_format_markdown_booking(booking))

                result = "\n".join(lines)
            else:
                # JSON format with truncation info
                response = {
                    "total": total_count,
                    "count": len(truncated_bookings),
                    "offset": offset,
                    "has_more": True,
                    "truncated": True,
                    "truncated_from": bookings_count,
                    "next_offset": offset + len(truncated_bookings),
                    "note": f"Response truncated from {bookings_count} to {len(truncated_bookings)} bookings due to size limit. Use next_offset to fetch more.",
                    "bookings": truncated_bookings
                }
                result = json.dumps(response, indent=2)

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
        # Make API request - Beds24 uses query param "id" not path param
        # Include invoice items for complete booking details
        booking_data = await _make_api_request("bookings", params={
            "id": params.booking_id,
            "includeInvoiceItems": "true",
            "includeInfoItems": "true"
        })

        # API returns {success: true, data: [...], count: 1}
        if isinstance(booking_data, dict) and 'data' in booking_data:
            bookings = booking_data.get('data', [])
            if not bookings:
                return "Error: Booking not found."
            booking = bookings[0]
        else:
            booking = booking_data

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            result = _format_markdown_booking(booking)
        else:
            result = json.dumps(booking, indent=2)

        return result

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_get_bookings_by_master",
    annotations={
        "title": "Get Bookings by Master ID",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_get_bookings_by_master(params: GetBookingsByMasterInput) -> str:
    """
    Get all bookings in a group by master booking ID.

    In Beds24, multi-room bookings are grouped together with a master booking ID.
    This tool retrieves all bookings that belong to the same group.

    Args:
        params (GetBookingsByMasterInput): Validated input parameters containing:
            - master_id (str): The master booking ID
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing all bookings in the group.

    Example:
        beds24_get_bookings_by_master(master_id="84062771")
    """
    try:
        # Query bookings by masterId
        booking_data = await _make_api_request("bookings", params={
            "masterId": params.master_id,
            "includeInvoiceItems": "true",
            "includeInfoItems": "true",
            "includeBookingGroup": "true"
        })

        # API returns {success: true, data: [...], count: N}
        if isinstance(booking_data, dict) and 'data' in booking_data:
            bookings = booking_data.get('data', [])
            if not bookings:
                return f"No bookings found with master ID: {params.master_id}"

            if params.response_format == ResponseFormat.MARKDOWN:
                lines = [f"## Booking Group (Master ID: {params.master_id})", ""]
                lines.append(f"**Total bookings in group:** {len(bookings)}")
                lines.append("")
                lines.append("---")
                for booking in bookings:
                    lines.append(_format_markdown_booking(booking))
                    lines.append("---")
                    lines.append("")
                result = "\n".join(lines)
            else:
                result = json.dumps({
                    "master_id": params.master_id,
                    "count": len(bookings),
                    "bookings": bookings
                }, indent=2)
            return result
        else:
            return json.dumps(booking_data, indent=2)

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
            - room_id (int): Beds24 room ID (required)
            - arrival (str): Arrival/check-in date (YYYY-MM-DD, required)
            - departure (str): Departure/check-out date (YYYY-MM-DD, required)
            - first_name (str): Guest's first name (required)
            - last_name (str): Guest's last name (required)
            - email (str): Guest's email address (required)
            - status (Optional[str]): Booking status (default: 'confirmed')
            - num_adult (Optional[int]): Number of adults (default: 1)
            - num_child (Optional[int]): Number of children (default: 0)
            - title (Optional[str]): Guest title (Mr/Mrs/Ms/Dr)
            - mobile (Optional[str]): Guest's phone number
            - address/city/state/postcode/country (Optional[str]): Guest address fields
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response containing created booking details with the following schema:

        Success response (JSON format):
        {
            "id": int,                    # New booking ID
            "status": str,                # Booking status
            "arrival": str,               # Arrival date
            "departure": str,             # Departure date
            "firstName": str,             # Guest first name
            "lastName": str,              # Guest last name
            "roomId": int,                # Room ID
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
        # Build booking data matching Beds24 v2 API structure
        booking_data: Dict[str, Any] = {
            "roomId": params.room_id,
            "arrival": params.arrival,
            "departure": params.departure,
            "firstName": params.first_name,
            "lastName": params.last_name,
            "email": params.email,
            "numAdult": params.num_adult,
            "numChild": params.num_child,
        }

        # Optional scalar fields
        optional_fields = {
            "status": params.status,
            "title": params.title,
            "phone": params.phone,
            "address": params.address,
            "city": params.city,
            "state": params.state,
            "postcode": params.postcode,
            "country": params.country,
            "channel": params.channel,
            "unitId": params.unit_id,
            "price": params.price,
            "commission": params.commission,
        }
        for key, val in optional_fields.items():
            if val is not None:
                booking_data[key] = val

        # Invoice items
        if params.invoice_items:
            booking_data['invoiceItems'] = [
                {k: v for k, v in {
                    "type": item.type,
                    "subType": item.sub_type,
                    "description": item.description,
                    "qty": item.qty,
                    "amount": item.amount,
                }.items() if v is not None}
                for item in params.invoice_items
            ]

        # Make API request - Beds24 expects array
        result = await _make_api_request("bookings", method="POST", json_data=[booking_data])

        # Handle array response - extract first item
        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            booking_id = result.get('id', 'N/A')
            status = result.get('status', params.status or 'confirmed')
            guest_name = f"{params.first_name} {params.last_name}".strip()

            lines = [
                "## Booking Created Successfully",
                "",
                f"**Booking ID:** {booking_id}",
                f"**Status:** {status}",
                f"**Arrival:** {params.arrival}",
                f"**Departure:** {params.departure}",
                f"**Guest:** {guest_name}",
                f"**Room ID:** {params.room_id}",
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
            - invoice_items (Optional[List]): Create or update invoice items.
                Each item: {id?, type?, description?, qty?, amount?, lineTotal?}
                - Omit 'id' to CREATE a new item (type required: 'charge' or 'payment')
                - Include 'id' to UPDATE an existing item
                Example: [{"id": 153898114, "qty": 2, "amount": 500000}]
                Example: [{"type": "charge", "description": "Extra fee", "qty": 1, "amount": 100000}]
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
        # Beds24 v2: update via POST /bookings with id in body
        update_data = {"id": params.booking_id}

        # Beds24 API uses flat fields: firstName, lastName, email, phone (not nested guest object)
        if params.guest_name:
            name_parts = params.guest_name.strip().split(' ', 1)
            update_data['firstName'] = name_parts[0]
            if len(name_parts) > 1:
                update_data['lastName'] = name_parts[1]
        if params.guest_email:
            update_data['email'] = params.guest_email
        if params.guest_phone:
            update_data['phone'] = params.guest_phone

        if params.number_of_guests is not None:
            update_data['numberOfGuests'] = params.number_of_guests
        if params.check_in:
            update_data['arrival'] = params.check_in
        if params.check_out:
            update_data['departure'] = params.check_out
        if params.special_requests:
            update_data['infoItems'] = [{"code": "NOTES", "text": params.special_requests}]
        if params.status:
            update_data['status'] = params.status
        if params.invoice_items:
            update_data['invoiceItems'] = [
                {k: v for k, v in {
                    "id": item.id,
                    "description": item.description,
                    "qty": item.qty,
                    "amount": item.amount,
                    "lineTotal": item.line_total
                }.items() if v is not None}
                for item in params.invoice_items
            ]

        # Make API request - send as array
        result = await _make_api_request(
            "bookings",
            method="POST",
            json_data=[update_data]
        )

        # Handle array response - extract first item
        if isinstance(result, list) and len(result) > 0:
            result = result[0]

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
            if params.invoice_items:
                updated_fields.append(f"Invoice items ({len(params.invoice_items)} item(s))")

            for field in updated_fields:
                lines.append(f"- ✅ {field}")

            if not updated_fields:
                lines.append("- No fields were updated (no changes provided)")

            result_str = "\n".join(lines)
        else:
            result['updated_fields'] = [
                k for k in ['guest_name', 'guest_email', 'guest_phone',
                           'number_of_guests', 'check_in', 'check_out',
                           'special_requests', 'status', 'invoice_items']
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
        "destructiveHint": False,
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
        # Beds24 v2: cancel by updating status to "cancelled" via POST /bookings
        cancel_data = {
            "id": params.booking_id,
            "status": "cancelled"
        }
        if params.cancellation_reason:
            cancel_data['infoItems'] = [{"code": "NOTES", "text": f"Cancellation: {params.cancellation_reason}"}]

        # Make API request - send as array
        result = await _make_api_request(
            "bookings",
            method="POST",
            json_data=[cancel_data]
        )

        # Handle array response - extract first item
        if isinstance(result, list) and len(result) > 0:
            result = result[0]

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            booking_id = result.get('id', params.booking_id) if isinstance(result, dict) else params.booking_id
            refund_amount = result.get('refundAmount', 0) if isinstance(result, dict) else 0

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
            response_data = result if isinstance(result, dict) else {}
            response_data['message'] = 'Booking cancelled successfully'
            result_str = json.dumps(response_data, indent=2)

        return result_str

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="beds24_delete_booking",
    annotations={
        "title": "Delete Booking",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def beds24_delete_booking(params: DeleteBookingInput) -> str:
    """
    Permanently delete a booking from Beds24.

    This tool permanently removes a booking from the system. This action cannot be undone.
    Use with caution - consider using beds24_cancel_booking instead if you want to keep
    the booking record for reporting purposes.

    Args:
        params (DeleteBookingInput): Validated input parameters containing:
            - booking_id (str): The booking ID to delete (required)
            - response_format (ResponseFormat): Output format (default: markdown)

    Returns:
        str: Formatted response confirming deletion

    Examples:
        - Use when: "Permanently delete booking BOOK-12345"
        - Use when: "Remove booking 67890 completely from the system"
        - Don't use when: You want to keep booking record (use beds24_cancel_booking instead)

    Error Handling:
        - Returns "Error: Resource not found" if booking ID doesn't exist
        - Returns "Error: Cannot delete booking" if booking is protected
        - Returns formatted deletion confirmation or error message
    """
    try:
        # Make API request - DELETE /bookings?id={booking_id}
        result = await _make_api_request(
            f"bookings?id={params.booking_id}",
            method="DELETE"
        )

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = [
                f"## 🗑️ Booking Deleted Permanently",
                "",
                f"**Booking ID:** {params.booking_id}",
                "",
                "⚠️ **Warning:** This booking has been permanently removed from the system and cannot be recovered.",
                ""
            ]

            if isinstance(result, dict) and result:
                lines.append("**Details:**")
                lines.append(f"```json")
                lines.append(json.dumps(result, indent=2))
                lines.append(f"```")

            result_str = "\n".join(lines)
        else:
            response_data = result if isinstance(result, dict) else {}
            response_data['message'] = 'Booking deleted permanently'
            response_data['booking_id'] = params.booking_id
            result_str = json.dumps(response_data, indent=2)

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

        # API returns data in 'data' key, not 'properties'
        properties = data.get('data', [])
        total = data.get('count', len(properties))

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
                city = prop.get('city', 'N/A')
                country = prop.get('country', 'N/A')

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
        # Build query parameters matching Beds24 v2 API
        query_params: Dict[str, Any] = {
            'propertyId': params.property_id,
            'startDate': params.start_date,
            'endDate': params.end_date,
        }
        if params.room_id is not None:
            query_params['roomId'] = params.room_id

        # Make API request
        availability = await _make_api_request(
            "inventory/rooms/availability",
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
        # Build query parameters matching Beds24 v2 API
        query_params: Dict[str, Any] = {
            'propertyId': params.property_id,
            'startDate': params.start_date,
            'endDate': params.end_date,
            'includeNumAvail': str(params.include_num_avail).lower(),
            'includeMinStay': str(params.include_min_stay).lower(),
            'includeMaxStay': str(params.include_max_stay).lower(),
            'includeMultiplier': str(params.include_multiplier).lower(),
            'includeOverride': str(params.include_override).lower(),
            'includePrices': str(params.include_prices).lower(),
            'includeLinkedPrices': str(params.include_linked_prices).lower(),
            'includeChannels': str(params.include_channels).lower(),
        }
        if params.room_id is not None:
            query_params['roomId'] = params.room_id

        # Make API request
        calendar_data = await _make_api_request("inventory/rooms/calendar", params=query_params)

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
        # Build Beds24 v2 payload: array of {roomId, calendar: [...]}
        payload = []
        for room in params.rooms:
            calendar_entries = []
            for entry in room.calendar:
                cal: Dict[str, Any] = {
                    "from": entry.from_date,
                    "to": entry.to_date,
                }
                if entry.price1 is not None:
                    cal["price1"] = entry.price1
                if entry.price2 is not None:
                    cal["price2"] = entry.price2
                if entry.min_stay is not None:
                    cal["minStay"] = entry.min_stay
                if entry.max_stay is not None:
                    cal["maxStay"] = entry.max_stay
                if entry.num_avail is not None:
                    cal["numAvail"] = entry.num_avail
                if entry.override is not None:
                    cal["override"] = entry.override
                if entry.channels is not None:
                    cal["channels"] = entry.channels
                calendar_entries.append(cal)

            payload.append({
                "roomId": room.room_id,
                "calendar": calendar_entries,
            })

        # Make API request — POST array to flat endpoint
        result = await _make_api_request(
            "inventory/rooms/calendar",
            method="POST",
            json_data=payload
        )

        # Format response
        if params.response_format == ResponseFormat.MARKDOWN:
            room_summaries = []
            for room in params.rooms:
                ranges = [f"{e.from_date} → {e.to_date}" for e in room.calendar]
                room_summaries.append(f"- Room `{room.room_id}`: {', '.join(ranges)}")

            lines = [
                "## Calendar Updated Successfully",
                "",
                f"**Rooms updated:** {len(params.rooms)}",
                "",
                *room_summaries,
            ]
            result_str = "\n".join(lines)
        else:
            result_str = json.dumps(result if result else {"message": "Calendar updated successfully"}, indent=2)

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
# Authentication Tools
# ==============================================================================

class SetupFromInviteCodeInput(BaseModel):
    """Input model for setting up authentication from invite code."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    invite_code: str = Field(
        ...,
        description="Invite code generated from Beds24 (https://beds24.com/control3.php?pagetype=apiv2)"
    )
    device_name: Optional[str] = Field(
        default="MCP Server",
        description="Device name for the token (default: MCP Server)"
    )


@mcp.tool(
    name="beds24_setup_from_invite_code",
    annotations={
        "title": "Setup Authentication from Invite Code",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def beds24_setup_from_invite_code(params: SetupFromInviteCodeInput) -> str:
    """
    Setup authentication using an invite code from Beds24.

    This tool exchanges an invite code for a refresh token and automatically
    configures the server to use it. The refresh token is stored in memory
    and will be used to automatically obtain access tokens when needed.

    IMPORTANT: After running this tool, save the refresh_token to your .env file:
    echo "BEDS24_REFRESH_TOKEN=your_refresh_token" > .env

    Invite codes can be generated at: https://beds24.com/control3.php?pagetype=apiv2

    Args:
        params (SetupFromInviteCodeInput): Validated input parameters containing:
            - invite_code (str): The invite code from Beds24
            - device_name (Optional[str]): Device name for identification

    Returns:
        str: JSON response containing:
            - success (bool): Whether setup was successful
            - refresh_token (str): The refresh token (SAVE THIS to .env!)
            - message (str): Instructions for next steps

    Example:
        beds24_setup_from_invite_code(invite_code="your_code_here")
    """
    try:
        headers = {
            "code": params.invite_code
        }
        if params.device_name:
            headers["deviceName"] = params.device_name

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/authentication/setup",
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()

        refresh_token = result.get("refreshToken")
        if refresh_token:
            # Update the token manager with new refresh token
            _token_manager.update_refresh_token(refresh_token)

            return json.dumps({
                "success": True,
                "refresh_token": refresh_token,
                "access_token": result.get("token"),
                "expires_in": result.get("expiresIn"),
                "message": (
                    "Authentication setup successful!\n\n"
                    "IMPORTANT: Save the refresh_token to your .env file:\n"
                    f"echo \"BEDS24_REFRESH_TOKEN={refresh_token}\" > .env\n\n"
                    "Then restart the server: docker compose down && docker compose up -d"
                )
            }, indent=2)

        return json.dumps({
            "success": False,
            "error": "No refresh token in response",
            "response": result
        }, indent=2)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401 or e.response.status_code == 400:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", "")
            except:
                pass
            return json.dumps({
                "success": False,
                "error": f"Invalid or expired invite code: {error_detail}",
                "message": "Please generate a new code from https://beds24.com/control3.php?pagetype=apiv2"
            }, indent=2)
        return json.dumps({"success": False, "error": _handle_api_error(e)}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool(
    name="beds24_check_auth_status",
    annotations={
        "title": "Check Authentication Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def beds24_check_auth_status() -> str:
    """
    Check the current authentication status.

    This tool verifies if the server has a valid refresh token configured
    and can obtain access tokens. It also shows the token details if available.

    Returns:
        str: JSON response containing:
            - has_refresh_token (bool): Whether refresh token is configured
            - access_token_valid (bool): Whether current access token is valid
            - token_details (object): Details about the access token if valid

    Example:
        beds24_check_auth_status()
    """
    import time

    result = {
        "has_refresh_token": bool(_token_manager._refresh_token),
        "refresh_token_set": "BEDS24_REFRESH_TOKEN env var is set" if _token_manager._refresh_token else "BEDS24_REFRESH_TOKEN env var is NOT set",
        "cached_access_token": bool(_token_manager._access_token),
        "token_expires_in": max(0, int(_token_manager._expires_at - time.time())) if _token_manager._access_token else 0
    }

    # Try to get/refresh access token to verify it works
    try:
        access_token = await _token_manager.get_access_token()
        result["access_token_valid"] = True

        # Get token details from API
        async with httpx.AsyncClient() as client:
            details_response = await client.get(
                f"{API_BASE_URL}/authentication/details",
                headers={"token": access_token},
                timeout=30.0
            )
            if details_response.status_code == 200:
                result["token_details"] = details_response.json()

    except Exception as e:
        result["access_token_valid"] = False
        result["error"] = str(e)

        if "BEDS24_REFRESH_TOKEN not set" in str(e):
            result["message"] = (
                "No refresh token configured. "
                "Run beds24_setup_from_invite_code with an invite code, "
                "or set BEDS24_REFRESH_TOKEN in your .env file."
            )
        elif "Invalid or expired" in str(e):
            result["message"] = (
                "Refresh token is invalid or expired. "
                "Please generate a new invite code from "
                "https://beds24.com/control3.php?pagetype=apiv2"
            )

    return json.dumps(result, indent=2)


# ==============================================================================
# Main Entry Point
# ==============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Beds24 MCP Server")
    parser.add_argument("--transport", type=str, default="stdio", choices=["stdio", "streamable-http"])
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    if args.transport == "streamable-http":
        import uvicorn
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route
        from starlette.responses import JSONResponse
        from starlette.requests import Request

        mcp_app = mcp.http_app(path="/mcp")

        async def _health(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok", "server": "beds24-mcp"})

        app = Starlette(
            lifespan=mcp_app.lifespan,
            routes=[
                Route("/health", _health, methods=["GET"]),
                # Mount MCP at root - it handles /mcp internally
                Mount("/", app=mcp_app),
            ],
        )

        uvicorn.run(app, host="0.0.0.0", port=args.port, proxy_headers=True, forwarded_allow_ips="*")
    else:
        mcp.run()
