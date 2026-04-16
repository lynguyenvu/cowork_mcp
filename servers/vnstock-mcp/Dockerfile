FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# Expose port for HTTP transport
EXPOSE 8002

# Run the server
CMD ["python", "server.py", "--transport", "streamable-http", "--port", "8002"]
