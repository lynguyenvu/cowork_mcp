FROM node:20-alpine

WORKDIR /app

# Install dependencies first (cache layer)
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Copy source and build
COPY tsconfig.json ./
COPY src/ ./src/
RUN node --max-old-space-size=1024 node_modules/.bin/tsc

# Auth credentials volume mount point
RUN mkdir -p /app/auth_info

EXPOSE 8769

ENV TRANSPORT=streamable-http
ENV PORT=8769
ENV NODE_ENV=production

CMD ["node", "dist/index.js"]
