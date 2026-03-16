# Human MCP Skill for OpenClaw

## Description

AI-powered browser automation skill using Google Gemini and Playwright. This skill enables OpenClaw to perform web automation, take screenshots, extract web content, and interact with websites using natural language.

## Capabilities

- **AI Automation**: Use Google Gemini for intelligent web interactions
- **Browser Automation**: Full Playwright support for browser control
- **Screenshot**: Capture page screenshots and elements
- **Web Scraping**: Extract data from websites
- **Form Automation**: Fill forms, click buttons, navigate

## Configuration

Set your Google Gemini API key in environment:

```bash
export GOOGLE_GEMINI_API_KEY=your_gemini_api_key_here
```

Optional additional API keys:
```bash
export MINIMAX_API_KEY=your_minimax_key
export ELEVENLABS_API_KEY=your_elevenlabs_key
export ZHIPU_API_KEY=your_zhipu_key
export RMBG_API_KEY=your_rmbg_key
```

## Tools

### Browser Tools
- `browser_navigate` - Navigate to a URL
- `browser_screenshot` - Take a screenshot
- `browser_click` - Click an element
- `browser_fill` - Fill form fields
- `browser_evaluate` - Execute JavaScript

### AI Tools
- `ai_complete` - Generate text with Gemini
- `ai_vision` - Analyze images

### Utility Tools
- `wait` - Wait for specified duration
- `extract_data` - Extract structured data from page

## Usage Examples

### Navigate and Screenshot
```
Take a screenshot of google.com
```

### Extract Data
```
Extract all product titles from example.com/shop
```

### Fill Form
```
Fill the contact form on example.com/contact with name: John, email: john@example.com
```

## API Documentation

- Google Gemini API: https://ai.google.dev/docs
- Human MCP: https://www.npmjs.com/package/@goonnguyen/human-mcp

## Notes

- This skill requires the Human MCP server to be running
- Default endpoint: http://localhost:3100 (direct) or http://localhost:8768 (via gateway)
- Requires Google Gemini API key for AI features
- Playwright browser must be installed (included in Docker image)

## Author

Claude Code

## License

MIT