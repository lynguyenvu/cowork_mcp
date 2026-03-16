#!/usr/bin/env python3
"""
Human MCP HTTP Gateway for OpenClaw

This script creates an HTTP API gateway that translates REST requests
to MCP tool calls for Human MCP server using Streamable HTTP transport.

Usage:
    python human-mcp-gateway.py [--port 8768] [--mcp-url http://localhost:3100]
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
MCP_URL = os.getenv("HUMAN_MCP_URL", "http://localhost:3100")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8768"))
DEFAULT_AUTH_TOKEN = os.getenv("GOOGLE_GEMINI_API_KEY", "")

app = FastAPI(
    title="Human MCP Gateway",
    description="HTTP API Gateway for Human MCP Server (AI + Browser Automation)",
    version="1.0.0"
)

# Session storage (in-memory, resets on restart)
_mcp_session_id: Optional[str] = None


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
            "clientInfo": {"name": "human-gateway", "version": "1.0"}
        }
    }

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"
    }

    try:
        response = await client.post(
            f"{MCP_URL}/mcp",
            json=init_payload,
            headers=headers,
            timeout=30.0
        )

        # Get session ID from response header
        session_id = response.headers.get("mcp-session-id") or response.headers.get("Mcp-Session-Id")
        if session_id:
            _mcp_session_id = session_id
            return session_id
    except Exception as e:
        print(f"Failed to init session: {e}")

    return None


async def call_mcp_tool(tool_name: str, params: Dict[str, Any], auth_token: str = None) -> Dict[str, Any]:
    """Call an MCP tool via streamable HTTP transport."""
    try:
        async with httpx.AsyncClient() as client:
            # Initialize session if needed
            await init_mcp_session(client)

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": params
                }
            }

            headers = {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json"
            }

            if _mcp_session_id:
                headers["mcp-session-id"] = _mcp_session_id

            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

            response = await client.post(
                f"{MCP_URL}/mcp",
                json=payload,
                headers=headers,
                timeout=120.0
            )

            # Handle SSE response
            text = response.text
            if 'text/event-stream' in response.headers.get('content-type', ''):
                # Parse SSE
                lines = text.strip().split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data = line[6:]
                        try:
                            result = json.loads(data)
                            if 'result' in result:
                                return result['result']
                        except json.JSONDecodeError:
                            continue

            return response.json()

    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "human-mcp-gateway",
        "mcp_url": MCP_URL,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Human MCP Gateway",
        "description": "AI + Browser Automation (Gemini + Playwright)",
        "version": "1.0.0",
        "mcp_url": MCP_URL,
        "endpoints": [
            "/health",
            "/tools",
            "/tools/{tool_name}"
        ]
    }


@app.get("/tools")
async def list_tools():
    """List available Human MCP tools."""
    try:
        result = await call_mcp_tool("list_tools", {})
        return result
    except Exception as e:
        return {"error": str(e), "tools": []}


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    """Call a specific MCP tool."""
    try:
        params = await request.json()
        result = await call_mcp_tool(tool_name, params, DEFAULT_AUTH_TOKEN)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Human MCP Gateway for OpenClaw")
    parser.add_argument("--port", type=int, default=GATEWAY_PORT, help="Gateway port")
    parser.add_argument("--mcp-url", type=str, default=MCP_URL, help="Human MCP URL")
    args = parser.parse_args()

    print(f"Starting Human MCP Gateway...")
    print(f"  Gateway: http://localhost:{args.port}")
    print(f"  MCP URL: {args.mcp_url}")

    uvicorn.run(app, host="0.0.0.0", port=args.port)