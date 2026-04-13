#!/usr/bin/env python3
"""
Baileys WhatsApp MCP HTTP Gateway for OpenClaw

Translates REST requests to MCP tool calls for the Baileys WhatsApp MCP server.
Uses stateless Streamable HTTP transport (no session ID required).

Usage:
    python baileys-mcp-gateway.py

Environment variables:
    GATEWAY_PORT       - Port to listen on (default: 8770)
    BAILEYS_MCP_URL    - Baileys MCP server URL (default: http://localhost:8769)
"""

import os
import json
import httpx
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, Request
import uvicorn

MCP_URL = os.getenv("BAILEYS_MCP_URL", "http://localhost:8769")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8770"))

app = FastAPI(
    title="Baileys WhatsApp MCP Gateway",
    description="HTTP API Gateway for Baileys WhatsApp MCP Server",
    version="1.0.0"
)

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json"
}


def parse_sse_response(text: str) -> dict[str, Any]:
    """Parse Server-Sent Events response and return the first data payload."""
    for line in text.strip().split('\n'):
        if line.startswith('data: '):
            try:
                return json.loads(line[6:])
            except json.JSONDecodeError:
                continue
    return {"error": "Could not parse SSE response", "raw": text[:500]}


async def call_mcp_tool(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Call an MCP tool via stateless Streamable HTTP. No session initialization needed."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": params}
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{MCP_URL}/mcp", json=payload, headers=MCP_HEADERS)
            response.raise_for_status()
            result = parse_sse_response(response.text)
            if "result" in result:
                content = result["result"].get("content", [])
                if content:
                    text_content = content[0].get("text", "")
                    try:
                        return json.loads(text_content)
                    except json.JSONDecodeError:
                        return {"result": text_content}
                return result["result"]
            if "error" in result:
                return {"error": result["error"]}
            return result
    except httpx.HTTPStatusError as e:
        return {"error": f"MCP server error {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


# ── Health & status ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Gateway health check. Also proxies WhatsApp connection status."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{MCP_URL}/health")
            wa_status = r.json()
    except Exception:
        wa_status = {"error": "MCP server unreachable"}
    return {"status": "ok", "service": "baileys-mcp-gateway", "whatsapp": wa_status}


@app.get("/qr")
async def get_qr():
    """Get QR code for WhatsApp authentication. Scan with WhatsApp mobile app."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{MCP_URL}/qr")
            return r.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MCP server unreachable: {e}")


# ── Generic tool proxy ───────────────────────────────────────────────────────

@app.get("/tools")
async def list_tools():
    """List all available WhatsApp MCP tools."""
    return {"tools": [
        {"name": "whatsapp_get_status",              "category": "connection",  "description": "Get WhatsApp connection status and QR code"},
        {"name": "whatsapp_logout",                  "category": "connection",  "description": "Logout and clear session"},
        {"name": "whatsapp_send_text",               "category": "messaging",   "description": "Send text message"},
        {"name": "whatsapp_send_image",              "category": "messaging",   "description": "Send image from URL or base64"},
        {"name": "whatsapp_send_document",           "category": "messaging",   "description": "Send document from URL"},
        {"name": "whatsapp_send_audio",              "category": "messaging",   "description": "Send audio from URL"},
        {"name": "whatsapp_send_video",              "category": "messaging",   "description": "Send video from URL"},
        {"name": "whatsapp_send_reaction",           "category": "messaging",   "description": "React to a message with emoji"},
        {"name": "whatsapp_send_poll",               "category": "messaging",   "description": "Send poll message"},
        {"name": "whatsapp_delete_message",          "category": "messaging",   "description": "Delete a message"},
        {"name": "whatsapp_get_messages",            "category": "messaging",   "description": "Get recent messages"},
        {"name": "whatsapp_check_number",            "category": "contacts",    "description": "Check if phone has WhatsApp"},
        {"name": "whatsapp_list_groups",             "category": "groups",      "description": "List all groups"},
        {"name": "whatsapp_get_group_info",          "category": "groups",      "description": "Get group details"},
        {"name": "whatsapp_create_group",            "category": "groups",      "description": "Create a new group"},
        {"name": "whatsapp_add_participants",        "category": "groups",      "description": "Add members to group"},
        {"name": "whatsapp_remove_participants",     "category": "groups",      "description": "Remove members from group"},
        {"name": "whatsapp_update_group_subject",    "category": "groups",      "description": "Update group name"},
        {"name": "whatsapp_update_group_description","category": "groups",      "description": "Update group description"},
        {"name": "whatsapp_get_invite_link",         "category": "groups",      "description": "Get group invite link"},
        {"name": "whatsapp_leave_group",             "category": "groups",      "description": "Leave a group"},
    ]}


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request):
    """Call any WhatsApp MCP tool by name with JSON body as arguments."""
    try:
        params = await request.json()
    except Exception:
        params = {}
    result = await call_mcp_tool(tool_name, params)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ── Convenience REST endpoints ───────────────────────────────────────────────

@app.post("/messages/text")
async def send_text(request: Request):
    """Send a text message. Body: {jid, text, mentions?}"""
    params = await request.json()
    return await call_mcp_tool("whatsapp_send_text", params)


@app.post("/messages/image")
async def send_image(request: Request):
    """Send an image. Body: {jid, url?, base64?, caption?, mimeType?}"""
    params = await request.json()
    return await call_mcp_tool("whatsapp_send_image", params)


@app.post("/messages/document")
async def send_document(request: Request):
    """Send a document. Body: {jid, url, fileName?, caption?}"""
    params = await request.json()
    return await call_mcp_tool("whatsapp_send_document", params)


@app.post("/messages/reaction")
async def send_reaction(request: Request):
    """React to a message. Body: {jid, messageId, emoji}"""
    params = await request.json()
    return await call_mcp_tool("whatsapp_send_reaction", params)


@app.post("/messages/poll")
async def send_poll(request: Request):
    """Send a poll. Body: {jid, question, options, allowMultiple?}"""
    params = await request.json()
    return await call_mcp_tool("whatsapp_send_poll", params)


@app.get("/messages")
async def get_messages(jid: Optional[str] = None, limit: int = 20):
    """Get recent messages. Query: ?jid=...&limit=20"""
    params: dict[str, Any] = {"limit": limit}
    if jid:
        params["jid"] = jid
    return await call_mcp_tool("whatsapp_get_messages", params)


@app.get("/contacts/check")
async def check_number(phone: str):
    """Check if phone number has WhatsApp. Query: ?phone=84987654321"""
    return await call_mcp_tool("whatsapp_check_number", {"phones": [phone]})


@app.get("/groups")
async def list_groups():
    """List all groups."""
    return await call_mcp_tool("whatsapp_list_groups", {})


@app.get("/groups/{group_jid}")
async def get_group(group_jid: str):
    """Get group details by JID."""
    return await call_mcp_tool("whatsapp_get_group_info", {"jid": group_jid})


@app.post("/groups")
async def create_group(request: Request):
    """Create a group. Body: {name, participants}"""
    params = await request.json()
    return await call_mcp_tool("whatsapp_create_group", params)


@app.post("/groups/{group_jid}/participants/add")
async def add_participants(group_jid: str, request: Request):
    """Add participants. Body: {participants: [...phones]}"""
    body = await request.json()
    return await call_mcp_tool("whatsapp_add_participants", {"jid": group_jid, **body})


@app.post("/groups/{group_jid}/participants/remove")
async def remove_participants(group_jid: str, request: Request):
    """Remove participants. Body: {participants: [...phones]}"""
    body = await request.json()
    return await call_mcp_tool("whatsapp_remove_participants", {"jid": group_jid, **body})


@app.get("/groups/{group_jid}/invite")
async def get_invite_link(group_jid: str):
    """Get group invite link."""
    return await call_mcp_tool("whatsapp_get_invite_link", {"jid": group_jid})


if __name__ == "__main__":
    print(f"[Baileys Gateway] Starting on port {GATEWAY_PORT}")
    print(f"[Baileys Gateway] MCP server: {MCP_URL}")
    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT)
