#!/usr/bin/env python3
"""
VNStock MCP Server - Model Context Protocol server for Vietnamese stock market data.

Provides LLMs with access to Vietnamese and global market data via the vnstock library:
- Historical & intraday price data
- Company information & financials
- Market listings & industry classification
- Real-time price boards
- Forex, crypto, and world index data

Authentication:
- Optional: Set VNSTOCK_API_KEY for enhanced vnstock data access
- Set VNSTOCK_SOURCE to choose data source (VCI or KBS, default: VCI)
- Simple mode: Set MCP_ACCESS_TOKEN for static Bearer token auth
- OAuth mode: Set OAUTH_CLIENT_ID + OAUTH_CLIENT_SECRET for OAuth 2.0 Authorization Code flow
  Endpoints: GET /oauth/authorize, POST /oauth/token, GET /.well-known/oauth-authorization-server

Author: Claude Code
"""

import argparse
import hashlib
import io
import json
import logging
import os
import secrets
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import pandas as pd
from fastmcp import FastMCP

# ==============================================================================
# Configuration
# ==============================================================================

VNSTOCK_API_KEY = os.environ.get("VNSTOCK_API_KEY", "")
DEFAULT_SOURCE = os.environ.get("VNSTOCK_SOURCE", "VCI")
SERVER_HOST = os.environ.get("VNSTOCK_MCP_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("VNSTOCK_MCP_PORT", "8002"))
# Simple Bearer token auth (static). If set, all /mcp requests require:
#   Authorization: Bearer <MCP_ACCESS_TOKEN>
MCP_ACCESS_TOKEN = os.environ.get("MCP_ACCESS_TOKEN", "")

# OAuth 2.0 credentials. If set, enables Authorization Code flow at /oauth/*
OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
OAUTH_TOKEN_TTL = int(os.environ.get("OAUTH_TOKEN_TTL", "3600"))  # seconds

# Public base URL for OAuth metadata (e.g. https://stock.the-emer.com)
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://stock.the-emer.com")

# In-memory stores — resets on restart, fine for single-user usage
# auth_code -> {client_id, redirect_uri, code_challenge, expires_at}
_auth_codes: dict = {}
# access_token -> {client_id, expires_at}
_oauth_tokens: dict = {}

# Suppress vnstock/vnai verbose logging
logging.getLogger("vnstock").setLevel(logging.WARNING)
logging.getLogger("vnai").setLevel(logging.WARNING)

# ==============================================================================
# MCP Server
# ==============================================================================

mcp = FastMCP(
    "vnstock-mcp",
    instructions=(
        "Vietnamese stock market data — historical prices, company financials, "
        "real-time boards, plus forex, crypto, and world index data."
    ),
)

# ==============================================================================
# API Key Registration
# ==============================================================================

_api_key_registered = False


def _ensure_api_key():
    """Register VNSTOCK_API_KEY once, suppressing stdout noise."""
    global _api_key_registered
    if _api_key_registered or not VNSTOCK_API_KEY:
        return
    _api_key_registered = True
    try:
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            from vnstock import register_user
            register_user(api_key=VNSTOCK_API_KEY)
        finally:
            sys.stdout = old_stdout
    except Exception:
        pass


# ==============================================================================
# Shared Helpers
# ==============================================================================

def _df_to_records(df) -> list[dict]:
    """Convert DataFrame / dict / Series to list of plain dicts.

    Handles: NaN, Timestamps, MultiIndex columns, tuple keys, Series, nested lists.
    """
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    if isinstance(df, pd.DataFrame):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ["_".join(str(c) for c in col).strip("_") for col in df.columns]
        df = df.where(pd.notnull(df), None)
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype(str)
        return df.to_dict(orient="records")
    if isinstance(df, dict):
        clean = {}
        for k, v in df.items():
            key = "_".join(str(c) for c in k) if isinstance(k, tuple) else str(k)
            clean[key] = v
        return [clean]
    if isinstance(df, pd.Series):
        return _df_to_records(df.to_frame())
    if isinstance(df, (list, tuple)):
        results = []
        for item in df:
            results.extend(_df_to_records(item))
        return results
    return [{"result": str(df)}]


def _default_dates(start: Optional[str], end: Optional[str]) -> tuple[str, str]:
    """Return (start, end) defaulting to last 30 days if not provided."""
    if not end:
        end = datetime.now().strftime("%Y-%m-%d")
    if not start:
        start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    return start, end


def _safe_call(fn, *args, **kwargs) -> list[dict]:
    """Call fn(*args, **kwargs) and return error dict on exception."""
    try:
        return _df_to_records(fn(*args, **kwargs))
    except Exception as e:
        return [{"error": str(e)}]


def _suppress_stdout(fn, *args, **kwargs):
    """Call fn with stdout redirected to /dev/null (vnstock/vnai prints noise)."""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        return fn(*args, **kwargs)
    finally:
        sys.stdout = old_stdout


def _get_stock(symbol: str, source: str = DEFAULT_SOURCE):
    """Return a Vnstock stock object for symbol."""
    _ensure_api_key()
    from vnstock import Vnstock
    vs = Vnstock(source=source, show_log=False)
    return vs.stock(symbol=symbol, source=source)


def _to_json(data: list[dict]) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


# ==============================================================================
# Quote Tools
# ==============================================================================

@mcp.tool()
def stock_history(
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "1D",
    source: str = DEFAULT_SOURCE,
) -> str:
    """Get historical OHLCV price data for a Vietnamese stock.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB, VCB)
        start: Start date YYYY-MM-DD (default: 30 days ago)
        end: End date YYYY-MM-DD (default: today)
        interval: 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M (default: 1D)
        source: VCI or KBS (default: VCI)
    """
    start, end = _default_dates(start, end)
    stock = _get_stock(symbol, source)
    data = _safe_call(stock.quote.history, start=start, end=end, interval=interval)
    return _to_json(data)


@mcp.tool()
def stock_intraday(
    symbol: str,
    page_size: int = 100,
    source: str = DEFAULT_SOURCE,
) -> str:
    """Get intraday (today's) trading data for a stock.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        page_size: Number of records to return (default: 100)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    data = _safe_call(stock.quote.intraday, page_size=page_size)
    return _to_json(data)


@mcp.tool()
def stock_price_depth(
    symbol: str,
    source: str = DEFAULT_SOURCE,
) -> str:
    """Get order book / price depth (bid/ask levels) for a stock.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    data = _safe_call(stock.quote.price_depth)
    return _to_json(data)


# ==============================================================================
# Company Tools
# ==============================================================================

@mcp.tool()
def company_overview(symbol: str, source: str = DEFAULT_SOURCE) -> str:
    """Get company overview: industry, market cap, description, exchange.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    return _to_json(_safe_call(stock.company.overview))


@mcp.tool()
def company_shareholders(symbol: str, source: str = DEFAULT_SOURCE) -> str:
    """Get major shareholders of a company.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    return _to_json(_safe_call(stock.company.shareholders))


@mcp.tool()
def company_officers(symbol: str, source: str = DEFAULT_SOURCE) -> str:
    """Get company officers / management team.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    return _to_json(_safe_call(stock.company.officers))


@mcp.tool()
def company_news(symbol: str, source: str = DEFAULT_SOURCE) -> str:
    """Get latest news about a company.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    return _to_json(_safe_call(stock.company.news))


@mcp.tool()
def company_events(symbol: str, source: str = DEFAULT_SOURCE) -> str:
    """Get company events: dividends, AGM dates, earnings announcements.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    return _to_json(_safe_call(stock.company.events))


# ==============================================================================
# Financial Tools
# ==============================================================================

@mcp.tool()
def financial_balance_sheet(
    symbol: str,
    period: str = "quarter",
    source: str = DEFAULT_SOURCE,
) -> str:
    """Get balance sheet data for a company.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        period: quarter or annual (default: quarter)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    return _to_json(_safe_call(stock.finance.balance_sheet, period=period))


@mcp.tool()
def financial_income_statement(
    symbol: str,
    period: str = "quarter",
    source: str = DEFAULT_SOURCE,
) -> str:
    """Get income statement (P&L) data for a company.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        period: quarter or annual (default: quarter)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    return _to_json(_safe_call(stock.finance.income_statement, period=period))


@mcp.tool()
def financial_cash_flow(
    symbol: str,
    period: str = "quarter",
    source: str = DEFAULT_SOURCE,
) -> str:
    """Get cash flow statement for a company.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        period: quarter or annual (default: quarter)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    return _to_json(_safe_call(stock.finance.cash_flow, period=period))


@mcp.tool()
def financial_ratio(
    symbol: str,
    period: str = "quarter",
    source: str = DEFAULT_SOURCE,
) -> str:
    """Get financial ratios (P/E, P/B, ROE, ROA, EPS, etc) for a company.

    Args:
        symbol: Stock ticker (e.g. VNM, FPT, ACB)
        period: quarter or annual (default: quarter)
        source: VCI or KBS (default: VCI)
    """
    stock = _get_stock(symbol, source)
    return _to_json(_safe_call(stock.finance.ratio, period=period))


# ==============================================================================
# Listing Tools
# ==============================================================================

@mcp.tool()
def listing_all_symbols(source: str = DEFAULT_SOURCE) -> str:
    """Get all listed stock symbols on Vietnamese exchanges (HOSE, HNX, UPCOM).

    Args:
        source: VCI or KBS (default: VCI)
    """
    _ensure_api_key()
    from vnstock.api.listing import Listing
    lst = Listing(source=source.lower())
    return _to_json(_safe_call(lst.all_symbols))


@mcp.tool()
def listing_symbols_by_group(group: str = "VN30", source: str = DEFAULT_SOURCE) -> str:
    """Get stock symbols in a market group.

    Args:
        group: VN30, HNX30, HOSE, HNX, UPCOM, VN100, VNALL (default: VN30)
        source: VCI or KBS (default: VCI)
    """
    _ensure_api_key()
    from vnstock.api.listing import Listing
    lst = Listing(source=source.lower())
    return _to_json(_safe_call(lst.symbols_by_group, group=group))


@mcp.tool()
def listing_symbols_by_exchange(source: str = DEFAULT_SOURCE) -> str:
    """Get stock symbols grouped by exchange (HOSE, HNX, UPCOM).

    Args:
        source: VCI or KBS (default: VCI)
    """
    _ensure_api_key()
    from vnstock.api.listing import Listing
    lst = Listing(source=source.lower())
    return _to_json(_safe_call(lst.symbols_by_exchange))


@mcp.tool()
def listing_industries(source: str = DEFAULT_SOURCE) -> str:
    """Get ICB industry classification for Vietnamese stocks.

    Args:
        source: VCI or KBS (default: VCI)
    """
    _ensure_api_key()
    from vnstock.api.listing import Listing
    lst = Listing(source=source.lower())
    return _to_json(_safe_call(lst.industries_icb))


# ==============================================================================
# Trading Tools
# ==============================================================================

@mcp.tool()
def trading_price_board(
    symbols: str,
    source: str = DEFAULT_SOURCE,
) -> str:
    """Get real-time price board for multiple stocks simultaneously.

    Args:
        symbols: Comma-separated tickers (e.g. "VNM,FPT,ACB,VCB")
        source: VCI or KBS (default: VCI)
    """
    _ensure_api_key()
    symbols_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    from vnstock.api.trading import Trading
    t = Trading(source=source.lower())
    return _to_json(_safe_call(t.price_board, symbols_list=symbols_list))


# ==============================================================================
# Global Market Tools
# ==============================================================================

@mcp.tool()
def fx_history(
    symbol: str = "EURUSD",
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "1D",
) -> str:
    """Get forex (currency pair) historical price data.

    Args:
        symbol: Currency pair e.g. EURUSD, GBPUSD, USDJPY (default: EURUSD)
        start: Start date YYYY-MM-DD (default: 30 days ago)
        end: End date YYYY-MM-DD (default: today)
        interval: 1D, 1W, 1M (default: 1D)
    """
    _ensure_api_key()
    start, end = _default_dates(start, end)
    try:
        from vnstock import Vnstock
        vs = _suppress_stdout(Vnstock, source="MSN", show_log=False)
        pair = vs.fx(symbol=symbol)
        df = pair.quote.history(start=start, end=end, interval=interval)
        return _to_json(_df_to_records(df))
    except Exception as e:
        return _to_json([{"error": str(e)}])


@mcp.tool()
def crypto_history(
    symbol: str = "BTC",
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "1D",
) -> str:
    """Get cryptocurrency historical price data.

    Args:
        symbol: Crypto ticker e.g. BTC, ETH, SOL (default: BTC)
        start: Start date YYYY-MM-DD (default: 30 days ago)
        end: End date YYYY-MM-DD (default: today)
        interval: 1D, 1W, 1M (default: 1D)
    """
    _ensure_api_key()
    start, end = _default_dates(start, end)
    try:
        from vnstock import Vnstock
        vs = _suppress_stdout(Vnstock, source="MSN", show_log=False)
        coin = vs.crypto(symbol=symbol)
        df = coin.quote.history(start=start, end=end, interval=interval)
        return _to_json(_df_to_records(df))
    except Exception as e:
        return _to_json([{"error": str(e)}])


@mcp.tool()
def world_index_history(
    symbol: str = "DJI",
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "1D",
) -> str:
    """Get world market index historical data.

    Args:
        symbol: DJI (Dow Jones), IXIC (NASDAQ), GSPC (S&P 500) (default: DJI)
        start: Start date YYYY-MM-DD (default: 30 days ago)
        end: End date YYYY-MM-DD (default: today)
        interval: 1D, 1W, 1M (default: 1D)
    """
    _ensure_api_key()
    start, end = _default_dates(start, end)
    try:
        from vnstock import Vnstock
        vs = _suppress_stdout(Vnstock, source="MSN", show_log=False)
        idx = vs.world_index(symbol=symbol)
        df = idx.quote.history(start=start, end=end, interval=interval)
        return _to_json(_df_to_records(df))
    except Exception as e:
        return _to_json([{"error": str(e)}])


@mcp.tool()
def fund_listing() -> str:
    """Get list of open-ended mutual funds available in Vietnam."""
    _ensure_api_key()
    try:
        from vnstock import Vnstock
        vs = Vnstock(show_log=False)
        f = vs.fund()
        return _to_json(_df_to_records(f.listing()))
    except Exception as e:
        return _to_json([{"error": str(e)}])


# ==============================================================================
# Entry Point
# ==============================================================================

# ==============================================================================
# OAuth 2.0 Helpers
# ==============================================================================

def _is_valid_oauth_token(token: str) -> bool:
    """Check if token exists in OAuth store and is not expired."""
    entry = _oauth_tokens.get(token)
    if not entry:
        return False
    if time.time() > entry["expires_at"]:
        del _oauth_tokens[token]
        return False
    return True


def _pkce_verify(code_verifier: str, code_challenge: str) -> bool:
    """Verify PKCE S256 code challenge."""
    import base64
    digest = hashlib.sha256(code_verifier.encode()).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return computed == code_challenge


# ==============================================================================
# Entry Point
# ==============================================================================

def _parse_args():
    parser = argparse.ArgumentParser(description="VNStock MCP Server")
    parser.add_argument("--transport", default="streamable-http", choices=["streamable-http", "stdio"])
    parser.add_argument("--port", type=int, default=SERVER_PORT)
    parser.add_argument("--host", default=SERVER_HOST)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        import uvicorn
        from starlette.applications import Starlette
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
        from starlette.routing import Mount, Route

        mcp_app = mcp.http_app(path="/mcp")

        # Public paths — always skip auth
        _PUBLIC_PATHS = {"/health", "/oauth/authorize", "/oauth/token", "/.well-known/oauth-authorization-server"}

        class BearerAuthMiddleware(BaseHTTPMiddleware):
            """Validate Bearer tokens on protected routes.

            Accepts:
            - Static MCP_ACCESS_TOKEN (simple mode)
            - OAuth 2.0 access tokens (OAuth mode)
            Public paths (/health, /oauth/*, /.well-known/*) are always allowed.
            """

            async def dispatch(self, request: Request, call_next) -> Response:
                # Always allow public paths
                if request.url.path in _PUBLIC_PATHS:
                    return await call_next(request)
                # No auth configured → open access
                if not MCP_ACCESS_TOKEN and not OAUTH_CLIENT_ID:
                    return await call_next(request)

                auth_header = request.headers.get("Authorization", "")
                if not auth_header.startswith("Bearer "):
                    return Response(
                        content='{"error": "Missing Authorization header"}',
                        status_code=401,
                        media_type="application/json",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                token = auth_header.removeprefix("Bearer ").strip()

                # Check static token
                if MCP_ACCESS_TOKEN and token == MCP_ACCESS_TOKEN:
                    return await call_next(request)
                # Check OAuth token
                if OAUTH_CLIENT_ID and _is_valid_oauth_token(token):
                    return await call_next(request)

                return Response(
                    content='{"error": "Invalid or expired token"}',
                    status_code=403,
                    media_type="application/json",
                )

        # --- OAuth routes ---

        async def _oauth_metadata(request: Request) -> JSONResponse:
            """RFC 8414 OAuth Authorization Server Metadata — used by Claude.ai to auto-discover endpoints."""
            return JSONResponse({
                "issuer": PUBLIC_URL,
                "authorization_endpoint": f"{PUBLIC_URL}/oauth/authorize",
                "token_endpoint": f"{PUBLIC_URL}/oauth/token",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["client_secret_post"],
            })

        async def _oauth_authorize(request: Request) -> Response:
            """OAuth 2.0 Authorization endpoint.

            Auto-approves for the configured client_id — no login UI needed
            for single-user setups. Validates client_id then redirects with code.
            """
            params = dict(request.query_params)
            client_id = params.get("client_id", "")
            redirect_uri = params.get("redirect_uri", "")
            state = params.get("state", "")
            code_challenge = params.get("code_challenge", "")
            code_challenge_method = params.get("code_challenge_method", "S256")
            response_type = params.get("response_type", "code")

            # Validate
            if not OAUTH_CLIENT_ID:
                return JSONResponse({"error": "OAuth not configured"}, status_code=503)
            if client_id != OAUTH_CLIENT_ID:
                return JSONResponse({"error": "invalid_client"}, status_code=401)
            if response_type != "code":
                return JSONResponse({"error": "unsupported_response_type"}, status_code=400)
            if not redirect_uri:
                return JSONResponse({"error": "missing redirect_uri"}, status_code=400)

            # Issue authorization code (valid 5 minutes)
            code = secrets.token_urlsafe(32)
            _auth_codes[code] = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
                "expires_at": time.time() + 300,
            }

            qs = urlencode({"code": code, "state": state} if state else {"code": code})
            return RedirectResponse(url=f"{redirect_uri}?{qs}", status_code=302)

        async def _oauth_token(request: Request) -> JSONResponse:
            """OAuth 2.0 Token endpoint — exchanges authorization code for access token."""
            form = await request.form()
            grant_type = form.get("grant_type", "")
            client_id = form.get("client_id", "")
            client_secret = form.get("client_secret", "")
            code = form.get("code", "")
            redirect_uri = form.get("redirect_uri", "")
            code_verifier = form.get("code_verifier", "")

            if not OAUTH_CLIENT_ID:
                return JSONResponse({"error": "OAuth not configured"}, status_code=503)
            if grant_type != "authorization_code":
                return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

            # Validate client credentials
            if client_id != OAUTH_CLIENT_ID or client_secret != OAUTH_CLIENT_SECRET:
                return JSONResponse({"error": "invalid_client"}, status_code=401)

            # Validate authorization code
            code_entry = _auth_codes.pop(code, None)
            if not code_entry:
                return JSONResponse({"error": "invalid_grant", "description": "Unknown or expired code"}, status_code=400)
            if time.time() > code_entry["expires_at"]:
                return JSONResponse({"error": "invalid_grant", "description": "Code expired"}, status_code=400)
            if code_entry["client_id"] != client_id:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            if redirect_uri and code_entry["redirect_uri"] != redirect_uri:
                return JSONResponse({"error": "invalid_grant", "description": "redirect_uri mismatch"}, status_code=400)

            # Verify PKCE if code_challenge was provided
            if code_entry.get("code_challenge"):
                if not code_verifier:
                    return JSONResponse({"error": "invalid_grant", "description": "code_verifier required"}, status_code=400)
                if not _pkce_verify(code_verifier, code_entry["code_challenge"]):
                    return JSONResponse({"error": "invalid_grant", "description": "PKCE verification failed"}, status_code=400)

            # Issue access token
            access_token = secrets.token_urlsafe(48)
            _oauth_tokens[access_token] = {
                "client_id": client_id,
                "expires_at": time.time() + OAUTH_TOKEN_TTL,
            }

            return JSONResponse({
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": OAUTH_TOKEN_TTL,
            })

        async def _health(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok", "server": "vnstock-mcp"})

        app = Starlette(
            lifespan=mcp_app.lifespan,
            routes=[
                Route("/health", _health, methods=["GET"]),
                Route("/.well-known/oauth-authorization-server", _oauth_metadata, methods=["GET"]),
                Route("/oauth/authorize", _oauth_authorize, methods=["GET"]),
                Route("/oauth/token", _oauth_token, methods=["POST"]),
                Mount("/", app=mcp_app),
            ],
        )
        app.add_middleware(BearerAuthMiddleware)

        uvicorn.run(app, host=args.host, port=args.port, proxy_headers=True, forwarded_allow_ips="*")
