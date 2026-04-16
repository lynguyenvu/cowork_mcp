#!/usr/bin/env python3
"""
Crawl4AI MCP Server

FastMCP server that wraps the Crawl4AI REST API, exposing web crawling
and scraping tools to MCP-compatible clients (e.g., GoClaw agents).

Tools exposed:
  - crawl4ai_md          : Convert URL to clean Markdown
  - crawl4ai_screenshot  : Capture full-page screenshot
  - crawl4ai_crawl       : Full crawl with custom config
  - crawl4ai_execute_js  : Execute JavaScript on a page
"""

import os
import json
import asyncio
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Crawl4AI REST API base URL (container name in goclaw_default network)
CRAWL4AI_BASE_URL = os.getenv("CRAWL4AI_BASE_URL", "http://crawl4ai-server:11235")
MCP_PORT = int(os.getenv("MCP_PORT", "8100"))
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
# Optional bearer token auth — set MCP_API_KEY env var to enable
MCP_API_KEY = os.getenv("MCP_API_KEY", "")

mcp = FastMCP("crawl4ai-mcp", host=MCP_HOST, port=MCP_PORT)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests without valid Bearer token when MCP_API_KEY is set."""

    async def dispatch(self, request: Request, call_next):
        if not MCP_API_KEY:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {MCP_API_KEY}":
            return Response("Unauthorized", status_code=401)
        return await call_next(request)


async def _post(endpoint: str, payload: dict) -> dict:
    """POST to crawl4ai REST API with timeout."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{CRAWL4AI_BASE_URL}{endpoint}", json=payload)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def crawl4ai_md(
    url: str,
    filter_type: str = "fit",
    query: str = None,
) -> str:
    """Convert a web page to clean Markdown.

    Args:
        url: Absolute http/https URL to fetch
        filter_type: Extraction mode — fit (default, readability), raw (full DOM),
                     bm25 (relevance ranking), llm (LLM summary)
        query: Optional query string for bm25/llm filter modes
    """
    payload = {"url": url, "f": filter_type}
    if query:
        payload["q"] = query

    result = await _post("/md", payload)

    if isinstance(result, dict):
        return result.get("markdown", result.get("content", json.dumps(result)))
    return str(result)


@mcp.tool()
async def crawl4ai_screenshot(
    url: str,
    output_path: str = None,
    wait_for_images: bool = True,
) -> str:
    """Capture a full-page PNG screenshot of a URL.

    Args:
        url: Absolute http/https URL to capture
        output_path: Optional server-side file path to save the screenshot
        wait_for_images: Wait for all images to load before capturing (default: true)
    """
    payload = {"url": url, "wait_for_images": wait_for_images}
    if output_path:
        payload["output_path"] = output_path

    result = await _post("/screenshot", payload)

    if isinstance(result, dict):
        path = result.get("path", result.get("output_path", ""))
        return f"Screenshot saved to: {path}" if path else json.dumps(result)
    return str(result)


@mcp.tool()
async def crawl4ai_execute_js(
    url: str,
    scripts: list[str],
) -> str:
    """Execute JavaScript snippets on a web page and return results.

    Args:
        url: Absolute http/https URL to load
        scripts: List of JavaScript code strings to execute in sequence
    """
    payload = {"url": url, "scripts": scripts}
    result = await _post("/execute_js", payload)

    if isinstance(result, dict):
        return json.dumps(result.get("results", result), ensure_ascii=False, indent=2)
    return str(result)


@mcp.tool()
async def crawl4ai_crawl(
    urls: list[str],
    word_count_threshold: int = 200,
    exclude_social_media: bool = True,
    remove_overlay_elements: bool = True,
    process_iframes: bool = False,
) -> str:
    """Full crawl of one or more URLs with structured output.

    Args:
        urls: List of URLs to crawl
        word_count_threshold: Minimum word count to keep a content block (default: 200)
        exclude_social_media: Remove social media links/content (default: true)
        remove_overlay_elements: Remove popups/overlays (default: true)
        process_iframes: Also process iframe content (default: false)
    """
    crawler_config = {
        "word_count_threshold": word_count_threshold,
        "exclude_social_media_links": exclude_social_media,
        "remove_overlay_elements": remove_overlay_elements,
        "process_iframes": process_iframes,
    }
    payload = {"urls": urls, "crawler_config": crawler_config}
    result = await _post("/crawl", payload)

    if isinstance(result, dict):
        results = result.get("results", [result])
        output = []
        for i, r in enumerate(results):
            url_info = r.get("url", urls[i] if i < len(urls) else "")
            success = r.get("success", False)
            markdown = r.get("markdown", {})
            if isinstance(markdown, dict):
                content = markdown.get("fit_markdown") or markdown.get("raw_markdown", "")
            else:
                content = str(markdown)
            output.append(f"## {url_info}\nStatus: {'✓' if success else '✗'}\n\n{content[:5000]}")
        return "\n\n---\n\n".join(output)
    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Add auth middleware if MCP_API_KEY is set
    if MCP_API_KEY:
        mcp.app.add_middleware(BearerAuthMiddleware)
    mcp.run(transport="streamable-http")
