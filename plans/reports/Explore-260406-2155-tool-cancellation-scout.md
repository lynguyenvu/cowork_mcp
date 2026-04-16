# Beds24 MCP Tool Cancellation Scout Report

**Date:** 2026-04-06  
**Task:** Scout beds24 MCP codebase for tool cancellation/error handling patterns  
**Status:** DONE

---

## Executive Summary

Investigated tool cancellation and error handling in Beds24 MCP server. Found **NO explicit "tool cancelled" error handling** at MCP protocol level. Instead, the codebase uses:

1. **httpx timeout handling** (30s per request)
2. **Broad exception catching** at tool level
3. **Graceful error formatting** via `_handle_api_error()`
4. **No cancellation tokens or abort mechanisms** for long-running operations

The "tool cancelled" errors likely originate from **FastMCP framework or MCP protocol layer** when tools exceed implicit timeouts, not from application code.

---

## Directory Structure

```
/cowork_mcp/
├── beds24-mcp-server/
│   ├── server.py (2868 lines) - Main MCP server
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── test_server.py
│   └── test-*.py (debug scripts)
└── openclaw-skills/beds24-mcp/
    ├── beds24-mcp-gateway.py - HTTP gateway wrapper
    ├── SKILL.md - Skill documentation
    └── README.md
```

---

## Files Analyzed

### 1. /cowork_mcp/beds24-mcp-server/server.py (Main Server)

**Size:** 2868 lines  
**Key Components:**

#### A. Error Handling Architecture (Lines 105-130)

```python
def _handle_api_error(e: Exception) -> str:
    """Consistent error formatting across all tools."""
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 404: ...
        elif e.response.status_code == 403: ...
        elif e.response.status_code == 401: ...
        elif e.response.status_code == 429: ...
        elif e.response.status_code == 400: ...
        return f"Error: API request failed with status {e.response.status_code}"
    elif isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Please try again."
    elif isinstance(e, httpx.ConnectError):
        return "Error: Failed to connect to Beds24 API. Please check your network connection."
    return f"Error: Unexpected error occurred: {type(e).__name__}"
```

**Observations:**
- Covers HTTP status errors, timeouts, connection errors
- Returns user-friendly error strings
- **No handling for `asyncio.CancelledError` or MCP cancellation tokens**

#### B. HTTP Request Timeouts (Lines 133-180)

All async HTTP requests use **30-second timeout**:

```python
async def _make_api_request(
    endpoint: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    ...
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{API_BASE_URL}/{endpoint}",
            headers=headers,
            params=params,
            json=json_data,
            timeout=30.0,  # <-- 30 second hard timeout
            **kwargs
        )
        response.raise_for_status()
        return response.json()
```

**Where Used:**
- Line 70: Token refresh
- Line 169: API requests (main function)
- Line 175: All tool calls via `_make_api_request()`
- Line 2715: Setup from invite code
- Line 2807: Check auth status

#### C. Token Manager (Lines 45-93)

```python
class TokenManager:
    async def get_access_token(self) -> str:
        """Get valid access token, refreshing if needed."""
        if self._access_token and time.time() < (self._expires_at - 300):
            return self._access_token
        
        if not self._refresh_token:
            raise ValueError("BEDS24_REFRESH_TOKEN not set...")
        
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
```

**Timeout Risk:** Token refresh also has 30s timeout - could fail if Beds24 API slow

#### D. Tool Exception Handlers (27 tools, all follow same pattern)

**Line ranges with try/except blocks:**
- 1079-1305: `beds24_list_bookings` (lines 1144-1303)
- 1307-1399: `beds24_get_booking` (lines 1371-1397)
- 1401-1466: `beds24_get_bookings_by_master` (lines 1429-1464)
- 1468-1579: `beds24_create_booking` (lines 1528-1577)
- 1581-1722: `beds24_update_booking` (lines 1636-1720)
- **1724-1821: `beds24_cancel_booking`** (lines 1776-1819) ✓
- 1827-1951: `beds24_list_properties` (lines 1886-1949)
- 1953-2034: `beds24_get_property` (lines 2020-2032)
- 2036-2161: `beds24_list_property_rooms` (lines 2098-2157)
- 2165-2258: `beds24_check_availability` (lines 2232-2256)
- 2260-2361: `beds24_get_calendar` (lines 2323-2359)
- 2363-2504: `beds24_update_calendar` (lines 2424-2502)
- 2506-2644: `beds24_get_pricing_offers` (lines 2572-2641)
- 2667-2759: `beds24_setup_from_invite_code` (lines 2704-2757)
- 2762-2829: `beds24_check_auth_status` (lines 2798-2814)

**Pattern (all identical):**
```python
@mcp.tool(name="beds24_<operation>")
async def beds24_<operation>(params: InputModel) -> str:
    try:
        # Validation
        # API call(s) via await _make_api_request(...)
        # Format response
        return result
    except Exception as e:
        return _handle_api_error(e)
```

**No handling for:**
- `asyncio.CancelledError`
- `asyncio.TimeoutError`
- Task cancellation from MCP protocol
- Long-running operations (list with 1000+ bookings)

#### E. Long-Running Operation Risk

Lines 1144-1200 in `beds24_list_bookings`:
```python
# pagination loop example (simplified)
while offset < max_offset:
    data = await _make_api_request("bookings", params=query_params)
    # process, increment offset
```

**Risk:** If loop iterates 10+ times (1000+ bookings), total time could exceed MCP timeout

#### F. MCP Server Initialization (Lines 2836-2867)

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Beds24 MCP Server")
    parser.add_argument("--transport", type=str, default="stdio", 
                       choices=["stdio", "streamable-http"])
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    if args.transport == "streamable-http":
        import uvicorn
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route
        ...
        mcp_app = mcp.http_app(path="/mcp")
        app = Starlette(lifespan=mcp_app.lifespan, routes=[...])
        uvicorn.run(app, host="0.0.0.0", port=args.port, 
                   proxy_headers=True, forwarded_allow_ips="*")
    else:
        mcp.run()
```

**Observations:**
- Uses FastMCP for stdio (default) or streamable-http
- Uvicorn has no explicit request timeout config
- No MCP protocol timeout handling

---

### 2. /cowork_mcp/beds24-mcp-server/Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
EXPOSE 8001
ENV BEDS24_API_BASE_URL=https://api.beds24.com/v2
CMD ["python", "server.py", "--transport", "streamable-http", "--port", "8001"]
```

**Note:** No timeout environment variables, no graceful shutdown handlers

---

### 3. /cowork_mcp/beds24-mcp-server/docker-compose.yml

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  interval: 30s
  timeout: 10s      # <-- Container-level timeout
  retries: 3
  start_period: 10s
```

**Observations:**
- Container health check: 10s timeout
- Tool request timeout: 30s (in code)
- No explicit MCP protocol timeout config

---

### 4. /cowork_mcp/openclaw-skills/beds24-mcp/beds24-mcp-gateway.py

**Size:** 428 lines  
**Purpose:** HTTP gateway wrapper for MCP tools (converts REST → MCP)

#### Key Error Handling (Lines 84-155)

```python
async def call_mcp_tool(tool_name: str, params: Dict[str, Any], 
                        auth_token: str = None) -> Dict[str, Any]:
    """Call an MCP tool via Streamable HTTP transport."""
    global _mcp_session_id

    try:
        headers = {...}
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

        async with httpx.AsyncClient(timeout=60.0) as client:  # <-- 60s timeout
            if not _mcp_session_id:
                await init_mcp_session(client)
            
            response = await client.post(
                f"{MCP_URL}/mcp",
                json=payload,
                headers=headers
            )

            # Handle session errors
            if response.status_code == 400 and "session" in response.text.lower():
                await init_mcp_session(client)
                if _mcp_session_id:
                    headers["mcp-session-id"] = _mcp_session_id
                    response = await client.post(...)

            response.raise_for_status()
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
```

**Timeout:** 60 seconds (longer than server's 30s per request)  
**Error Handling:** Broad catch-all, returns `{"error": str(e)}`

**No handling for:**
- SSE stream interruption
- MCP protocol errors
- Cancellation tokens

---

### 5. /cowork_mcp/beds24-mcp-server/test_server.py

**Lines 116-206:** Error handling test suite

```python
def test_error_handling():
    """Test error handling utilities."""
    # Tests for:
    # - 404 errors (line 128-143)
    # - 401 errors (line 145-160)
    # - 429 rate limits (line 162-177)
    # - Timeouts (line 179-190) ✓
    # - Connection errors (line 192-203)
```

**Timeout test (line 179-190):**
```python
print("\n4. Testing timeout handling...")
try:
    raise httpx.TimeoutException("Request timed out")
except Exception as e:
    result = _handle_api_error(e)
    if "timeout" in result.lower() or "timed out" in result.lower():
        print(f"   ✅ Correctly handled timeout")
```

**Observation:** Tests `httpx.TimeoutException` but NOT `asyncio.CancelledError` or MCP-level timeouts

---

## Tool Cancellation Handling Analysis

### Where "Tool Cancelled" Could Come From

1. **FastMCP Framework** - Likely source
   - May timeout tool execution if response takes too long
   - No explicit timeout config in beds24 server

2. **MCP Protocol Layer** - Implicit timeout
   - Client may cancel if server doesn't respond quickly enough
   - No cancellation token support in current code

3. **httpx Library** - Explicit 30s timeout
   - Raises `httpx.TimeoutException` (caught by `_handle_api_error`)
   - Doesn't directly cause "tool cancelled" but could trigger FastMCP timeout

4. **Uvicorn/Starlette** - Request-level timeout
   - No explicit timeout config (uses defaults)
   - Could terminate request if too slow

### Current Error Handling Coverage

**✓ Covered:**
- HTTP status errors (404, 401, 403, 429, 400)
- httpx timeout exceptions
- Connection errors
- Generic exceptions → error string

**✗ NOT Covered:**
- `asyncio.CancelledError` - No catch
- `asyncio.TimeoutError` - No catch
- `asyncio.TaskGroup` cancellation
- MCP protocol-level cancellation
- Graceful shutdown on cancellation

---

## Code Patterns That Could Cause Cancellation

### 1. Long-Running List Operations

**File:** `/cowork_mcp/beds24-mcp-server/server.py:1089-1305`

```python
async def beds24_list_bookings(params: ListBookingsInput) -> str:
    try:
        # ... pagination loop ...
        while offset < max_offset:
            data = await _make_api_request("bookings", params=query_params)
            # ... process results ...
            offset = next_offset
        # ... format response ...
```

**Risk:** 
- 10+ API calls × 30s each = 5+ minutes total
- MCP client likely times out after 60s or so
- Result: "tool cancelled"

### 2. Token Refresh Timeout

**File:** `/cowork_mcp/beds24-mcp-server/server.py:70-75`

```python
response = await client.get(
    f"{API_BASE_URL}/authentication/token",
    headers={"refreshToken": self._refresh_token},
    timeout=30.0
)
```

**Risk:**
- If Beds24 API slow, 30s timeout fires
- Raises `httpx.TimeoutException`
- Tool returns error message instead of result

### 3. Async Context Manager Exit

**File:** `/cowork_mcp/beds24-mcp-server/server.py:168-178`

```python
async with httpx.AsyncClient() as client:
    response = await client.request(
        method, ..., timeout=30.0, **kwargs
    )
    response.raise_for_status()
    return response.json()
# <-- AsyncClient context exit here
```

**Risk:** If task cancelled during context exit, cleanup might fail

---

## Timeout Configuration Summary

| Component | Timeout | Location | Handling |
|-----------|---------|----------|----------|
| **httpx request** | 30s | `_make_api_request()` | ✓ `_handle_api_error()` |
| **httpx request** | 30s | Token refresh | ✓ `_handle_api_error()` |
| **httpx request** | 30s | Auth check | ✓ `_handle_api_error()` |
| **Gateway client** | 60s | `call_mcp_tool()` | ✓ broad `except` |
| **Container health** | 10s | docker-compose | (health check only) |
| **MCP protocol** | ??? | FastMCP | ✗ **UNKNOWN** |
| **Uvicorn** | default | uvicorn | ✗ **NO CONFIG** |

---

## Async Patterns Observed

### Pattern 1: Async Tool Decorator
**Lines:** 1079, 1307, 1401, 1468, 1581, 1724, 1827, 1953, 2036, 2165, 2260, 2363, 2506, 2667, 2762

```python
@mcp.tool(name="beds24_<operation>")
async def beds24_<operation>(params: InputModel) -> str:
    try:
        await _make_api_request(...)
    except Exception as e:
        return _handle_api_error(e)
```

### Pattern 2: No Cancellation Token Support
**Observed:** No `asyncio.CancelToken`, `contextvars.Context`, or manual cancellation checks

### Pattern 3: Sync Exception Handler for Async Operation
**Lines:** 1303, 1397, 1464, 1577, 1720, 1819, 1949, 2032, 2157, 2256, 2359, 2502, 2641, 2757, 2814

Broad `except Exception` catches both sync and async exceptions, but doesn't distinguish cancellation:

```python
except Exception as e:
    return _handle_api_error(e)  # Treats all exceptions same
```

---

## Cancellation Handling Gaps

1. **No `asyncio.CancelledError` handling**
   - If MCP client cancels, exception propagates uncaught
   - No opportunity to clean up resources

2. **No graceful timeout on pagination**
   - `beds24_list_bookings` loops without timeout check
   - Could exceed MCP timeout on large result sets

3. **No cancellation token propagation**
   - Can't signal to nested `_make_api_request()` to abort
   - Each API call completes 30s timeout even if tool cancelled

4. **No task group management**
   - If parallel requests needed in future, no structure for cancellation

5. **No request deadline**
   - Tool could theoretically run indefinitely (no MCP-level deadline)

---

## Recommended Investigation Points

1. **FastMCP source code** - Check default timeout for tool execution
2. **MCP protocol spec** - Look for cancellation/timeout in spec
3. **Client behavior** - Reproduce "tool cancelled" with long-running query
4. **Server logs** - Add debug logging to catch exception type

---

## Files Relevant to This Investigation

| File | Path | Size | Relevance |
|------|------|------|-----------|
| server.py | `/cowork_mcp/beds24-mcp-server/server.py` | 2868 lines | ⭐⭐⭐ PRIMARY |
| beds24-mcp-gateway.py | `/cowork_mcp/openclaw-skills/beds24-mcp/beds24-mcp-gateway.py` | 428 lines | ⭐⭐ SECONDARY |
| docker-compose.yml | `/cowork_mcp/beds24-mcp-server/docker-compose.yml` | 36 lines | ⭐ CONFIG |
| Dockerfile | `/cowork_mcp/beds24-mcp-server/Dockerfile` | 22 lines | ⭐ CONFIG |
| test_server.py | `/cowork_mcp/beds24-mcp-server/test_server.py` | 328 lines | ⭐ TESTS |

---

## Unresolved Questions

1. What is the default MCP protocol timeout? (Not documented in code)
2. Does FastMCP have configurable timeout per tool?
3. What exception type does MCP client send when cancelling?
4. Should pagination be split into separate tool calls for large sets?
5. Is token refresh happening inside tool call or before?

