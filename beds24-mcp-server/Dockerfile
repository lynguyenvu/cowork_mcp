FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# Expose port for HTTP transport
EXPOSE 8001

# Set environment variables
ENV BEDS24_API_BASE_URL=https://api.beds24.com/v2

# Run the server
CMD ["python", "server.py", "--transport", "streamable-http", "--port", "8001"]