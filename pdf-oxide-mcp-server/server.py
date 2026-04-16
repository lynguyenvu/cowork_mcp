"""PDF Oxide MCP Server - PDF extraction tools for AI assistants."""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Initialize MCP server
mcp = FastMCP("pdf_oxide")

# Constants
DEFAULT_PAGE = 0
MAX_TEXT_LENGTH = 50000


class PDFInfo(BaseModel):
    """PDF document information."""
    page_count: int = Field(description="Number of pages in the PDF")
    version: str = Field(description="PDF version (e.g., '1.4')")
    title: Optional[str] = Field(default=None, description="Document title")
    author: Optional[str] = Field(default=None, description="Document author")
    subject: Optional[str] = Field(default=None, description="Document subject")
    creator: Optional[str] = Field(default=None, description="Application that created the PDF")
    producer: Optional[str] = Field(default=None, description="Application that produced the PDF")


class ExtractTextInput(BaseModel):
    """Input for text extraction."""
    file_path: str = Field(description="Path to the PDF file")
    page: Optional[int] = Field(default=None, description="Page number (0-indexed). If not specified, extract from all pages.")
    start_page: Optional[int] = Field(default=None, description="Start page for range extraction (0-indexed)")
    end_page: Optional[int] = Field(default=None, description="End page for range extraction (0-indexed, exclusive)")


class ExtractMarkdownInput(BaseModel):
    """Input for Markdown conversion."""
    file_path: str = Field(description="Path to the PDF file")
    page: Optional[int] = Field(default=None, description="Page number (0-indexed)")
    detect_headings: bool = Field(default=True, description="Detect headings in the PDF")
    start_page: Optional[int] = Field(default=None, description="Start page for range extraction")
    end_page: Optional[int] = Field(default=None, description="End page for range extraction")


class ExtractHtmlInput(BaseModel):
    """Input for HTML conversion."""
    file_path: str = Field(description="Path to the PDF file")
    page: Optional[int] = Field(default=None, description="Page number (0-indexed)")
    start_page: Optional[int] = Field(default=None, description="Start page for range extraction")
    end_page: Optional[int] = Field(default=None, description="End page for range extraction")


class ExtractImagesInput(BaseModel):
    """Input for image extraction."""
    file_path: str = Field(description="Path to the PDF file")
    page: Optional[int] = Field(default=None, description="Page number (0-indexed)")
    output_dir: str = Field(default="./pdf_images", description="Directory to save extracted images")


class SearchPdfInput(BaseModel):
    """Input for PDF search."""
    file_path: str = Field(description="Path to the PDF file")
    pattern: str = Field(description="Regex pattern to search for")
    case_sensitive: bool = Field(default=False, description="Case sensitive search")


class ExtractWordsInput(BaseModel):
    """Input for word extraction."""
    file_path: str = Field(description="Path to the PDF file")
    page: int = Field(description="Page number (0-indexed)")


class ExtractTablesInput(BaseModel):
    """Input for table extraction."""
    file_path: str = Field(description="Path to the PDF file")
    page: int = Field(description="Page number (0-indexed)")


def truncate_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Truncate text to maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + f"\n\n[Truncated - {len(text) - max_length} characters omitted]"


@mcp.tool()
def get_pdf_info(file_path: str) -> Dict[str, Any]:
    """Get PDF document information including page count, version, and metadata.

    Args:
        file_path: Path to the PDF file

    Returns:
        Dictionary with page_count, version, and optional metadata fields
    """
    from pdf_oxide import PdfDocument

    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        with PdfDocument(file_path) as doc:
            info = {
                "page_count": doc.page_count(),
                "version": doc.version(),
            }

            # Try to get metadata
            try:
                meta = doc.get_metadata()
                if meta:
                    if meta.title:
                        info["title"] = meta.title
                    if meta.author:
                        info["author"] = meta.author
                    if meta.subject:
                        info["subject"] = meta.subject
                    if meta.creator:
                        info["creator"] = meta.creator
                    if meta.producer:
                        info["producer"] = meta.producer
            except Exception:
                pass

            return info
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def extract_text(file_path: str, page: Optional[int] = None, start_page: Optional[int] = None, end_page: Optional[int] = None) -> str:
    """Extract plain text from a PDF document.

    Args:
        file_path: Path to the PDF file
        page: Specific page number to extract from (0-indexed). If not specified, uses start_page/end_page or all pages.
        start_page: Start page for range extraction (0-indexed)
        end_page: End page for range extraction (0-indexed, exclusive)

    Returns:
        Extracted text content from the PDF
    """
    from pdf_oxide import PdfDocument

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        with PdfDocument(file_path) as doc:
            if page is not None:
                text = doc.extract_text(page)
            elif start_page is not None and end_page is not None:
                texts = []
                for p in range(start_page, min(end_page, doc.page_count())):
                    texts.append(doc.extract_text(p))
                text = "\n\n".join(texts)
            else:
                # Extract from all pages
                texts = []
                for p in range(doc.page_count()):
                    texts.append(doc.extract_text(p))
                text = "\n\n".join(texts)

            return truncate_text(text)
    except Exception as e:
        return f"Error extracting text: {str(e)}"


@mcp.tool()
def extract_markdown(file_path: str, page: Optional[int] = None, detect_headings: bool = True, start_page: Optional[int] = None, end_page: Optional[int] = None) -> str:
    """Convert PDF page(s) to Markdown format with layout preservation.

    Args:
        file_path: Path to the PDF file
        page: Specific page number to convert (0-indexed)
        detect_headings: Whether to detect and convert headings
        start_page: Start page for range extraction
        end_page: End page for range extraction

    Returns:
        Markdown formatted text
    """
    from pdf_oxide import PdfDocument, ToMarkdownOptions

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        options = ToMarkdownOptions(detect_headings=detect_headings)

        with PdfDocument(file_path) as doc:
            if page is not None:
                markdown = doc.to_markdown(page, options)
            elif start_page is not None and end_page is not None:
                markdowns = []
                for p in range(start_page, min(end_page, doc.page_count())):
                    markdowns.append(doc.to_markdown(p, options))
                markdown = "\n\n---\n\n".join(markdowns)
            else:
                markdowns = []
                for p in range(doc.page_count()):
                    markdowns.append(doc.to_markdown(p, options))
                markdown = "\n\n---\n\n".join(markdowns)

            return truncate_text(markdown)
    except Exception as e:
        return f"Error converting to markdown: {str(e)}"


@mcp.tool()
def extract_html(file_path: str, page: Optional[int] = None, start_page: Optional[int] = None, end_page: Optional[int] = None) -> str:
    """Convert PDF page(s) to HTML format.

    Args:
        file_path: Path to the PDF file
        page: Specific page number to convert (0-indexed)
        start_page: Start page for range extraction
        end_page: End page for range extraction

    Returns:
        HTML formatted text
    """
    from pdf_oxide import PdfDocument, ToHtmlOptions

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        options = ToHtmlOptions()

        with PdfDocument(file_path) as doc:
            if page is not None:
                html = doc.to_html(page, options)
            elif start_page is not None and end_page is not None:
                htmls = []
                for p in range(start_page, min(end_page, doc.page_count())):
                    htmls.append(doc.to_html(p, options))
                html = "\n".join(htmls)
            else:
                htmls = []
                for p in range(doc.page_count()):
                    htmls.append(doc.to_html(p, options))
                html = "\n".join(htmls)

            return truncate_text(html, max_length=100000)
    except Exception as e:
        return f"Error converting to HTML: {str(e)}"


@mcp.tool()
def extract_images(file_path: str, page: Optional[int] = None, output_dir: str = "./pdf_images") -> Dict[str, Any]:
    """Extract images from PDF pages.

    Args:
        file_path: Path to the PDF file
        page: Specific page number to extract images from (0-indexed)
        output_dir: Directory to save extracted images

    Returns:
        Dictionary with extracted image information
    """
    from pdf_oxide import PdfDocument
    import uuid

    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        with PdfDocument(file_path) as doc:
            pages_to_extract = [page] if page is not None else range(doc.page_count())

            results = []
            for p in pages_to_extract:
                images = doc.extract_images(p)
                for idx, img in enumerate(images):
                    # Save image
                    image_id = str(uuid.uuid4())[:8]
                    ext = img.get("format", "png").lower()
                    if ext == "jpeg":
                        ext = "jpg"
                    filename = f"page{p}_img{idx}_{image_id}.{ext}"
                    filepath = output_path / filename

                    with open(filepath, "wb") as f:
                        f.write(img["data"])

                    results.append({
                        "page": p,
                        "image_index": idx,
                        "filename": filename,
                        "path": str(filepath),
                        "width": img.get("width"),
                        "height": img.get("height"),
                        "format": img.get("format"),
                    })

            return {
                "output_dir": str(output_path),
                "image_count": len(results),
                "images": results
            }
    except Exception as e:
        return {"error": f"Error extracting images: {str(e)}"}


@mcp.tool()
def search_pdf(file_path: str, pattern: str, case_sensitive: bool = False) -> Dict[str, Any]:
    """Search for text matching a regex pattern in a PDF.

    Args:
        file_path: Path to the PDF file
        pattern: Regular expression pattern to search for
        case_sensitive: Whether the search should be case-sensitive

    Returns:
        Dictionary with search results including matches and their positions
    """
    from pdf_oxide import PdfDocument
    import re

    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    flags = 0 if case_sensitive else re.IGNORECASE

    try:
        compiled_pattern = re.compile(pattern, flags)

        with PdfDocument(file_path) as doc:
            results = []
            for page_num in range(doc.page_count()):
                text = doc.extract_text(page_num)
                matches = compiled_pattern.finditer(text)

                for match in matches:
                    # Get surrounding context
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]

                    results.append({
                        "page": page_num,
                        "match": match.group(),
                        "position": match.start(),
                        "context": f"...{context}...",
                        "full_line": text.split('\n')[max(0, text[:match.start()].count('\n') - 1):text[:match.end()].count('\n') + 1]
                    })

            return {
                "pattern": pattern,
                "case_sensitive": case_sensitive,
                "total_matches": len(results),
                "matches": results[:100]  # Limit to first 100 matches
            }
    except Exception as e:
        return {"error": f"Error searching PDF: {str(e)}"}


@mcp.tool()
def extract_words(file_path: str, page: int) -> List[Dict[str, Any]]:
    """Extract individual words with their positions from a PDF page.

    Args:
        file_path: Path to the PDF file
        page: Page number (0-indexed)

    Returns:
        List of words with text and bounding box coordinates
    """
    from pdf_oxide import PdfDocument

    path = Path(file_path)
    if not path.exists():
        return [{"error": f"File not found: {file_path}"}]

    try:
        with PdfDocument(file_path) as doc:
            if page < 0 or page >= doc.page_count():
                return [{"error": f"Invalid page number: {page}. PDF has {doc.page_count()} pages."}]

            words = doc.extract_words(page)
            return [
                {
                    "text": w.text,
                    "bbox": {
                        "x": w.bbox.x0,
                        "y": w.bbox.y0,
                        "width": w.bbox.x1 - w.bbox.x0,
                        "height": w.bbox.y1 - w.bbox.y0,
                    }
                }
                for w in words
            ]
    except Exception as e:
        return [{"error": f"Error extracting words: {str(e)}"}]


@mcp.tool()
def extract_tables(file_path: str, page: int) -> List[Dict[str, Any]]:
    """Extract tables from a PDF page.

    Args:
        file_path: Path to the PDF file
        page: Page number (0-indexed)

    Returns:
        List of extracted tables with row data
    """
    from pdf_oxide import PdfDocument

    path = Path(file_path)
    if not path.exists():
        return [{"error": f"File not found: {file_path}"}]

    try:
        with PdfDocument(file_path) as doc:
            if page < 0 or page >= doc.page_count():
                return [{"error": f"Invalid page number: {page}. PDF has {doc.page_count()} pages."}]

            tables = doc.extract_tables(page)

            results = []
            for table in tables:
                results.append({
                    "row_count": table.row_count,
                    "column_count": table.column_count,
                    "rows": [
                        [cell.text if cell.text else "" for cell in row.cells]
                        for row in table.rows
                    ]
                })

            return results
    except Exception as e:
        return [{"error": f"Error extracting tables: {str(e)}"}]


if __name__ == "__main__":
    import sys

    transport = "stdio"
    port = 8004

    # Parse command line arguments
    args = sys.argv[1:]
    if "--transport" in args:
        idx = args.index("--transport")
        if idx + 1 < len(args):
            transport = args[idx + 1]

    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            port = int(args[idx + 1])

    if transport == "streamable-http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")