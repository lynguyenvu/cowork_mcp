#!/usr/bin/env python3
"""
Pancake MCP HTTP Gateway for OpenClaw

This script creates an HTTP API gateway that translates REST requests
to MCP tool calls for Pancake MCP server.

Usage:
    python pancake-mcp-gateway.py [--port 8766] [--mcp-url http://localhost:8765]
"""

import os
import sys
import json
import httpx
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

# Configuration
MCP_URL = os.getenv("PANCAKE_MCP_URL", "http://localhost:8765")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8766"))
DEFAULT_AUTH_TOKEN = os.getenv("PANCAKE_ACCESS_TOKEN") or os.getenv("PANCAKE_API_KEY", "")

app = FastAPI(
    title="Pancake MCP Gateway",
    description="HTTP API Gateway for Pancake MCP Server",
    version="1.0.0"
)

async def call_mcp_tool(tool_name: str, params: Dict[str, Any], auth_token: str = None) -> Dict[str, Any]:
    """Call an MCP tool via HTTP transport."""
    try:
        # MCP HTTP transport expects JSON-RPC format
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            }
        }

        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MCP_URL}/mcp",
                json=payload,
                headers=headers,
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "pancake-mcp-gateway", "timestamp": datetime.now().isoformat()}

@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Pancake MCP Gateway",
        "version": "1.0.0",
        "mcp_url": MCP_URL,
        "endpoints": [
            "/health",
            "/tools",
            "/tools/{tool_name}",
            "/shops",
            "/orders",
            "/conversations"
        ]
    }

@app.get("/tools")
async def list_tools():
    """List available Pancake MCP tools."""
    tools = [
        {"name": "get_shops", "description": "Get all shops"},
        {"name": "get_provinces", "description": "Get provinces"},
        {"name": "get_districts", "description": "Get districts"},
        {"name": "get_communes", "description": "Get communes"},
        {"name": "search_orders", "description": "Search orders"},
        {"name": "get_order", "description": "Get order details"},
        {"name": "create_order", "description": "Create order"},
        {"name": "list_conversations", "description": "List conversations"},
        {"name": "send_message", "description": "Send message"},
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

# Shop endpoints
@app.get("/shops")
async def get_shops():
    """Get all shops."""
    result = await call_mcp_tool("get_shops", {}, DEFAULT_AUTH_TOKEN)
    return result

@app.get("/provinces")
async def get_provinces():
    """Get all provinces."""
    result = await call_mcp_tool("get_provinces", {}, DEFAULT_AUTH_TOKEN)
    return result

# Order endpoints
@app.get("/orders")
async def search_orders(
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20
):
    """Search orders with filters."""
    params = {"limit": limit}
    if status:
        params["status"] = status
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date

    result = await call_mcp_tool("search_orders", params, DEFAULT_AUTH_TOKEN)
    return result

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get order details."""
    result = await call_mcp_tool("get_order", {"order_id": order_id}, DEFAULT_AUTH_TOKEN)
    return result

# Conversation endpoints
@app.get("/conversations")
async def list_conversations(
    status: Optional[str] = None,
    limit: int = 20
):
    """List conversations."""
    params = {"limit": limit}
    if status:
        params["status"] = status

    result = await call_mcp_tool("list_conversations", params, DEFAULT_AUTH_TOKEN)
    return result

@app.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, request: Request):
    """Send a message."""
    try:
        data = await request.json()
        params = {
            "conversation_id": conversation_id,
            "message": data.get("message", ""),
            "attachment_url": data.get("attachment_url")
        }
        result = await call_mcp_tool("send_message", params, DEFAULT_AUTH_TOKEN)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pancake MCP Gateway for OpenClaw")
    parser.add_argument("--port", type=int, default=GATEWAY_PORT, help="Gateway port")
    parser.add_argument("--mcp-url", type=str, default=MCP_URL, help="Pancake MCP URL")
    args = parser.parse_args()

    print(f"Starting Pancake MCP Gateway...")
    print(f"  Gateway: http://localhost:{args.port}")
    print(f"  MCP URL: {args.mcp_url}")

    uvicorn.run(app, host="0.0.0.0", port=args.port)