#!/usr/bin/env python3
"""
Beds24 MCP HTTP Gateway for OpenClaw

This script creates an HTTP API gateway that translates REST requests
to MCP tool calls for Beds24 MCP server using Streamable HTTP transport.

Usage:
    python beds24-mcp-gateway.py [--port 8767] [--mcp-url http://localhost:8001]
"""

import os
import json
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

# Configuration
MCP_URL = os.getenv("BEDS24_MCP_URL", "http://localhost:8001")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8767"))
DEFAULT_AUTH_TOKEN = os.getenv("BEDS24_API_TOKEN", "")

app = FastAPI(
    title="Beds24 MCP Gateway",
    description="HTTP API Gateway for Beds24 MCP Server",
    version="1.0.0"
)

# Session storage (in-memory, resets on restart)
_mcp_session_id: Optional[str] = None


def parse_sse_response(text: str) -> Dict[str, Any]:
    """Parse Server-Sent Events response."""
    lines = text.strip().split('\n')
    for line in lines:
        if line.startswith('data: '):
            data = line[6:]  # Remove 'data: ' prefix
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                continue
    return {"error": "Could not parse SSE response"}


async def init_mcp_session(client: httpx.AsyncClient) -> Optional[str]:
    """Initialize MCP session and return session ID."""
    global _mcp_session_id

    init_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "beds24-gateway", "version": "1.0"}
        }
    }

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"
    }

    response = await client.post(
        f"{MCP_URL}/mcp",
        json=init_payload,
        headers=headers
    )

    # Get session ID from response header
    session_id = response.headers.get("mcp-session-id") or response.headers.get("Mcp-Session-Id")
    if session_id:
        _mcp_session_id = session_id
        return session_id

    return _mcp_session_id


async def call_mcp_tool(tool_name: str, params: Dict[str, Any], auth_token: str = None) -> Dict[str, Any]:
    """Call an MCP tool via Streamable HTTP transport."""
    global _mcp_session_id

    try:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }

        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        if _mcp_session_id:
            headers["mcp-session-id"] = _mcp_session_id

        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            # If no session, initialize first
            if not _mcp_session_id:
                await init_mcp_session(client)
                if _mcp_session_id:
                    headers["mcp-session-id"] = _mcp_session_id

            response = await client.post(
                f"{MCP_URL}/mcp",
                json=payload,
                headers=headers
            )

            # Handle session errors
            if response.status_code == 400 and "session" in response.text.lower():
                # Re-initialize session
                await init_mcp_session(client)
                if _mcp_session_id:
                    headers["mcp-session-id"] = _mcp_session_id
                    response = await client.post(
                        f"{MCP_URL}/mcp",
                        json=payload,
                        headers=headers
                    )

            response.raise_for_status()

            # Parse SSE response
            text = response.text
            result = parse_sse_response(text)

            if "result" in result:
                content = result["result"].get("content", [])
                if content and len(content) > 0:
                    text_content = content[0].get("text", "")
                    try:
                        return json.loads(text_content)
                    except json.JSONDecodeError:
                        return {"result": text_content}
                return result["result"]
            elif "error" in result:
                return {"error": result["error"]}
            return result

    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "beds24-mcp-gateway", "timestamp": datetime.now().isoformat()}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Beds24 MCP Gateway",
        "version": "1.0.0",
        "mcp_url": MCP_URL,
        "endpoints": [
            "/health",
            "/tools",
            "/tools/{tool_name}",
            "/bookings",
            "/properties"
        ]
    }


@app.get("/tools")
async def list_tools():
    """List available Beds24 MCP tools."""
    tools = [
        {"name": "beds24_setup_from_invite_code", "description": "Setup auth from invite code"},
        {"name": "beds24_check_auth_status", "description": "Check authentication status"},
        {"name": "beds24_list_bookings", "description": "List bookings with filters"},
        {"name": "beds24_get_booking", "description": "Get booking details"},
        {"name": "beds24_create_booking", "description": "Create a new booking"},
        {"name": "beds24_update_booking", "description": "Update a booking"},
        {"name": "beds24_cancel_booking", "description": "Cancel a booking"},
        {"name": "beds24_list_properties", "description": "List properties"},
        {"name": "beds24_get_property", "description": "Get property details"},
        {"name": "beds24_list_property_rooms", "description": "List rooms in a property"},
        {"name": "beds24_check_availability", "description": "Check room availability"},
        {"name": "beds24_get_calendar", "description": "Get availability calendar"},
        {"name": "beds24_update_calendar", "description": "Update calendar"},
        {"name": "beds24_get_pricing_offers", "description": "Get pricing offers"},
    ]
    return {"tools": tools}


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    """Call a specific MCP tool."""
    try:
        params = await request.json()
        result = await call_mcp_tool(tool_name, params, DEFAULT_AUTH_TOKEN)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Booking endpoints
@app.get("/bookings")
async def list_bookings(
    property_id: Optional[str] = None,
    status: Optional[str] = None,
    check_in_from: Optional[str] = None,
    check_in_to: Optional[str] = None,
    limit: int = 50
):
    """List bookings with filters."""
    params = {"limit": limit}
    if property_id:
        params["propertyId"] = property_id
    if status:
        params["status"] = status
    if check_in_from:
        params["checkInFrom"] = check_in_from
    if check_in_to:
        params["checkInTo"] = check_in_to

    result = await call_mcp_tool("beds24_list_bookings", params, DEFAULT_AUTH_TOKEN)
    return result


@app.get("/bookings/{booking_id}")
async def get_booking(booking_id: str):
    """Get booking details."""
    result = await call_mcp_tool("beds24_get_booking", {"bookingId": booking_id}, DEFAULT_AUTH_TOKEN)
    return result


@app.post("/bookings")
async def create_booking(request: Request):
    """Create a new booking."""
    try:
        data = await request.json()
        result = await call_mcp_tool("beds24_create_booking", data, DEFAULT_AUTH_TOKEN)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/bookings/{booking_id}")
async def update_booking(booking_id: str, request: Request):
    """Update a booking."""
    try:
        data = await request.json()
        data["bookingId"] = booking_id
        result = await call_mcp_tool("beds24_update_booking", data, DEFAULT_AUTH_TOKEN)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/bookings/{booking_id}")
async def cancel_booking(booking_id: str, request: Request = None):
    """Cancel a booking."""
    try:
        reason = None
        if request:
            try:
                data = await request.json()
                reason = data.get("reason")
            except:
                pass

        params = {"bookingId": booking_id}
        if reason:
            params["reason"] = reason

        result = await call_mcp_tool("beds24_cancel_booking", params, DEFAULT_AUTH_TOKEN)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Authentication endpoints
@app.post("/auth/setup")
async def setup_from_invite_code(request: Request):
    """Setup authentication from invite code.

    Invite codes can be generated at: https://beds24.com/control3.php?pagetype=apiv2

    Returns refresh_token that should be saved to .env file.
    """
    try:
        data = await request.json()
        params = {"params": {"invite_code": data.get("invite_code")}}
        if data.get("device_name"):
            params["params"]["device_name"] = data.get("device_name")
        result = await call_mcp_tool("beds24_setup_from_invite_code", params, None)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/status")
async def check_auth_status():
    """Check current authentication status."""
    try:
        result = await call_mcp_tool("beds24_check_auth_status", {}, None)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Property endpoints
@app.get("/properties")
async def list_properties(limit: int = 50):
    """List properties."""
    result = await call_mcp_tool("beds24_list_properties", {"params": {"limit": limit}}, DEFAULT_AUTH_TOKEN)
    return result


@app.get("/properties/{property_id}")
async def get_property(property_id: str):
    """Get property details."""
    result = await call_mcp_tool("beds24_get_property", {"propertyId": property_id}, DEFAULT_AUTH_TOKEN)
    return result


@app.get("/properties/{property_id}/rooms")
async def list_property_rooms(property_id: str):
    """List rooms in a property."""
    result = await call_mcp_tool("beds24_list_property_rooms", {"propertyId": property_id}, DEFAULT_AUTH_TOKEN)
    return result


# Availability & Pricing
@app.get("/availability")
async def check_availability(
    property_id: str,
    room_id: Optional[str] = None,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    guests: int = 1
):
    """Check room availability."""
    params = {"propertyId": property_id, "guests": guests}
    if room_id:
        params["roomId"] = room_id
    if check_in:
        params["checkIn"] = check_in
    if check_out:
        params["checkOut"] = check_out

    result = await call_mcp_tool("beds24_check_availability", params, DEFAULT_AUTH_TOKEN)
    return result


@app.get("/calendar")
async def get_calendar(
    property_id: str,
    room_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """Get availability calendar."""
    params = {"propertyId": property_id}
    if room_id:
        params["roomId"] = room_id
    if year:
        params["year"] = year
    if month:
        params["month"] = month

    result = await call_mcp_tool("beds24_get_calendar", params, DEFAULT_AUTH_TOKEN)
    return result


@app.put("/calendar")
async def update_calendar(request: Request):
    """Update calendar availability."""
    try:
        data = await request.json()
        result = await call_mcp_tool("beds24_update_calendar", data, DEFAULT_AUTH_TOKEN)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pricing")
async def get_pricing_offers(
    property_id: str,
    room_id: Optional[str] = None,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    guests: int = 1
):
    """Get pricing offers."""
    params = {"propertyId": property_id, "guests": guests}
    if room_id:
        params["roomId"] = room_id
    if check_in:
        params["checkIn"] = check_in
    if check_out:
        params["checkOut"] = check_out

    result = await call_mcp_tool("beds24_get_pricing_offers", params, DEFAULT_AUTH_TOKEN)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Beds24 MCP Gateway for OpenClaw")
    parser.add_argument("--port", type=int, default=GATEWAY_PORT, help="Gateway port")
    parser.add_argument("--mcp-url", type=str, default=MCP_URL, help="Beds24 MCP URL")
    args = parser.parse_args()

    print(f"Starting Beds24 MCP Gateway...")
    print(f"  Gateway: http://localhost:{args.port}")
    print(f"  MCP URL: {args.mcp_url}")

    uvicorn.run(app, host="0.0.0.0", port=args.port)