# Plan: PDF Oxide MCP Server

## Overview
Tạo MCP server cho pdf_oxide - thư viện PDF extraction (text, markdown, HTML, images)

## Tools cần implement
1. `extract_text` - Trích xuất text từ PDF
2. `extract_markdown` - Chuyển đổi PDF sang Markdown
3. `extract_html` - Chuyển đổi PDF sang HTML
4. `extract_images` - Trích xuất hình ảnh từ PDF
5. `get_pdf_info` - Lấy thông tin PDF (số trang, version, metadata)
6. `extract_words` - Trích xuất từng từ với vị trí
7. `extract_tables` - Trích xuất bảng
8. `search_pdf` - Tìm kiếm text trong PDF (regex)

## Cấu trúc
```
pdf-oxide-mcp/
├── server.py          # MCP server chính
├── requirements.txt   # Dependencies
├── Dockerfile         # Docker container
├── docker-compose.yml # Docker compose
├── server.json        # MCP registry config
└── tools.json         # Tools definitions
```

## Dependencies
- fastmcp
- pdf_oxide (Python bindings)
- uvicorn

## Status: ✅ Completed