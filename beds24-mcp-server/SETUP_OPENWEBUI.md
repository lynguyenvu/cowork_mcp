# Bed24 MCP Server Installation & Setup for Open WebUI

This guide shows how to install and configure the Bed24 MCP Server to work with Open WebUI on the same server.

## Prerequisites

- Python 3.9 or higher
- Open WebUI installed and running
- Bed24 API token (Long Life Token or Refresh Token)

## Quick Setup

### 1. Install Dependencies

```bash
cd /cowork_mcp/beds24-mcp-server
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your Bed24 API token:

```bash
nano .env
```

Set these values:
```env
BEDS24_API_TOKEN=your_actual_token_here
BEDS24_API_BASE_URL=https://api.beds24.com/v2
```

### 3. Run the MCP Server

**Option A: Run as HTTP Server (Recommended for Production)**

```bash
python server.py --transport streamable-http --port 8001
```

**Option B: Run with systemd (Auto-restart on boot)**

Copy the systemd service file:

```bash
sudo cp beds24-mcp.service /etc/systemd/system/
sudo nano /etc/systemd/system/beds24-mcp.service  # Update API token
sudo systemctl enable --now beds24-mcp
sudo systemctl status beds24-mcp
```

**Option C: Run with tmux (For Development)**

```bash
tmux new -s beds24-mcp
python server.py --transport streamable-http --port 8001
# Detach with Ctrl+B then D
```

### 4. Configure Open WebUI

#### Method 1: Using Open WebUI Config File

1. Copy the config file to Open WebUI's MCP config directory:

```bash
cp config-openwebui.json /path/to/open-webui/backend/data/mcp/config.json
```

2. Update the API token in the config file:

```bash
nano /path/to/open-webui/backend/data/mcp/config.json
```

Replace `your_actual_api_token_here` with your real token.

3. Restart Open WebUI backend:

```bash
cd /path/to/open-webui/backend
./run.sh  # or restart your systemd service
```

#### Method 2: Using Open WebUI UI

1. Open Open WebUI in your browser
2. Go to **Settings** → **MCP Servers**
3. Click **Add MCP Server**
4. Fill in the details:
   - **Name**: `Beds24`
   - **Transport Type**: `HTTP`
   - **URL**: `http://localhost:8001`
   - **Environment Variables**:
     - `BEDS24_API_TOKEN`: `your_token_here`
     - `BEDS24_API_BASE_URL`: `https://api.beds24.com/v2`
5. Click **Save**

### 5. Verify Installation

Check if the server is running:

```bash
curl http://localhost:8001/health
```

You should see a health check response.

In Open WebUI, you should now see "Beds24" in the list of available MCP servers, and the 12 tools should be available for use.

## Usage in Open WebUI

Once configured, you can use the Beds24 tools in your chats:

### Example Queries:

**List bookings:**
```
Can you show me all confirmed bookings for property 12345?
```

**Create a booking:**
```
I need to create a booking for John Doe at property 12345 from March 15 to March 20. Guest email is john@example.com.
```

**Check availability:**
```
Are there any rooms available at property 12345 from March 20 to March 25 for 2 guests?
```

**Get pricing:**
```
What are the pricing offers for property 12345 for a 3-night stay in March?
```

## Troubleshooting

### Server won't start

Check the logs:
```bash
sudo journalctl -u beds24-mcp -f
```

Or if running in terminal:
```bash
python server.py --transport streamable-http --port 8001
```

### Open WebUI can't connect

1. Check if server is running:
```bash
curl http://localhost:8001
```

2. Check firewall:
```bash
sudo ufw allow 8001
```

3. Check Open WebUI logs:
```bash
docker logs open-webui-backend  # if using Docker
```

### Tools not showing up

1. Restart Open WebUI backend
2. Check MCP config file permissions
3. Verify API token is valid in `.env` file

## Running in Development Mode

For testing without HTTP server:

```bash
# Terminal 1: Run MCP server
cd /cowork_mcp/beds24-mcp-server
python server.py

# Terminal 2: Test with mcp CLI
mcp ping < server.py
```

## Update & Maintenance

### Update the server

```bash
cd /cowork_mcp/beds24-mcp-server
git pull  # if using git
pip install -r requirements.txt --upgrade
sudo systemctl restart beds24-mcp
```

### Monitor logs

```bash
# systemd logs
sudo journalctl -u beds24-mcp -f

# Or if running manually
tail -f /var/log/beds24-mcp.log
```

### Check server status

```bash
sudo systemctl status beds24-mcp
```

## Security Notes

- **Never commit `.env` file** with your API token to git
- Use strong API tokens and rotate them regularly
- Consider using a reverse proxy (nginx) with SSL for production
- Limit access to port 8001 to localhost only (firewall rules)

## Support

- Bed24 API Docs: https://wiki.beds24.com/index.php/Category:API_V2
- Open WebUI Docs: https://docs.openwebui.com/
- MCP Protocol: https://modelcontextprotocol.io
