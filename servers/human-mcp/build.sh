#!/bin/bash
#
# Build and run Human MCP Server with Playwright support
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Human MCP Server Build Script ==="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating from .env.example..."
    cat > .env << 'EOF'
# Required
GOOGLE_GEMINI_API_KEY=your_gemini_api_key_here

# Optional - for additional features
# MINIMAX_API_KEY=your_minimax_key
# ELEVENLABS_API_KEY=your_elevenlabs_key
# ZHIPU_API_KEY=your_zhipu_key
# RMBG_API_KEY=your_removebg_key
EOF
    echo "✅ Created .env file. Please edit it with your API keys."
    echo ""
    echo "📝 Please edit .env file and add your API keys, then run this script again."
    exit 1
fi

# Source the .env file
export $(grep -v '^#' .env | xargs) 2>/dev/null || true

# Check for required API key
if [ -z "$GOOGLE_GEMINI_API_KEY" ] || [ "$GOOGLE_GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
    echo "❌ GOOGLE_GEMINI_API_KEY not set!"
    echo "Please add your API key to .env file:"
    echo "  GOOGLE_GEMINI_API_KEY=your_actual_key"
    exit 1
fi

echo "✅ Environment configured"
echo ""

# Stop existing container
echo "🛑 Stopping existing container (if any)..."
docker stop human-mcp 2>/dev/null || true
docker rm human-mcp 2>/dev/null || true

# Build new image
echo "🔨 Building Docker image with Playwright support..."
docker compose build --no-cache

# Start container
echo "🚀 Starting Human MCP Server..."
docker compose up -d

echo ""
echo "=== Build Complete ==="
echo ""
echo "📊 Server Status:"
sleep 3
docker ps --filter "name=human-mcp" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🔗 Endpoints:"
echo "  Health: http://localhost:3100/health"
echo "  MCP:    http://localhost:3100/mcp"

echo ""
echo "✅ Human MCP Server is running!"
