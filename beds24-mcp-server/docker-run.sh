#!/bin/bash
# Build and run Beds24 MCP Server in Docker

set -e

IMAGE_NAME="beds24-mcp-server"
CONTAINER_NAME="beds24-mcp"

# Build the image
echo "Building Docker image..."
docker build -t $IMAGE_NAME .

# Stop existing container if running
if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "Stopping existing container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
fi

# Run the container
echo "Starting container..."
docker run -d \
    --name $CONTAINER_NAME \
    -p 8001:8001 \
    -e BEDS24_API_TOKEN="${BEDS24_API_TOKEN}" \
    --restart unless-stopped \
    $IMAGE_NAME

echo "Container started. Checking status..."
sleep 2
docker ps -f name=$CONTAINER_NAME

echo ""
echo "✅ Beds24 MCP Server is running on http://localhost:8001"
echo ""
echo "To view logs: docker logs -f $CONTAINER_NAME"
echo "To stop: docker stop $CONTAINER_NAME"