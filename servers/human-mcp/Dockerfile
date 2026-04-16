# Human MCP Server with Playwright Support
# Based on official Playwright image for full browser automation support

FROM mcr.microsoft.com/playwright:v1.50.1-noble

# Set working directory
WORKDIR /app

# Install Node.js 22 (if not already present in base image)
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Verify Node.js version
RUN node --version && npm --version

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /home/appuser -m appuser

# Set environment variables
ENV NODE_ENV=production
ENV PORT=3100

# Copy gateway
COPY gateway.js /app/gateway.js

# Switch to non-root user
USER appuser

# Set home directory for npm
ENV NPM_CONFIG_PREFIX=/home/appuser/.npm-global
ENV PATH=$PATH:/home/appuser/.npm-global/bin

# Pre-install human-mcp package to avoid npx download delay
RUN npm install -g @goonnguyen/human-mcp

# Expose port
EXPOSE 3100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3100/health', (r) => r.statusCode === 200 ? process.exit(0) : process.exit(1))"

# Start HTTP gateway
CMD ["node", "/app/gateway.js"]
