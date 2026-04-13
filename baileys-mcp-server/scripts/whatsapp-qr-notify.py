#!/usr/bin/env python3
"""
WhatsApp QR Notifier - Polls Baileys MCP for QR and sends to Telegram.

Usage:
    python3 whatsapp-qr-notify.py [--chat-id CHAT_ID] [--account ACCOUNT]

Environment:
    TELEGRAM_BOT_TOKEN - Bot token (required)
    TELEGRAM_CHAT_ID   - Default chat ID (optional, can override via --chat-id)
    BAILEYS_MCP_URL    - MCP server URL (default: http://localhost:8769)

To get your Telegram chat_id:
1. Start a DM with your bot
2. Send any message to the bot
3. Run: curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates?limit=1" | jq '.result[0].message.chat.id'
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

# Configuration
BAILEYS_MCP_URL = os.getenv("BAILEYS_MCP_URL", "http://localhost:8769")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# State file to track last QR code (avoid duplicate sends)
STATE_FILE = Path("/tmp/whatsapp-qr-state.json")


def log(msg: str):
    """Log to stderr."""
    print(f"[QR-Notify] {msg}", file=sys.stderr)


def fetch_qr(account: str = "default") -> dict:
    """Fetch QR code from Baileys MCP."""
    url = f"{BAILEYS_MCP_URL}/qr?account={account}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        log(f"Error fetching QR: {e}")
        return {"error": str(e)}
    except json.JSONDecodeError as e:
        log(f"Error parsing QR response: {e}")
        return {"error": str(e)}


def load_state() -> dict:
    """Load last QR state."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {"last_qr": "", "last_sent": 0}


def save_state(qr_code: str):
    """Save current QR state."""
    STATE_FILE.write_text(json.dumps({
        "last_qr": qr_code,
        "last_sent": time.time()
    }))


def qr_changed(qr_code: str, state: dict) -> bool:
    """Check if QR code changed since last check."""
    if qr_code != state.get("last_qr", ""):
        return True
    # Also send if > 5 minutes since last sent (QR expires)
    if time.time() - state.get("last_sent", 0) > 300:
        return True
    return False


def generate_qr_image(qr_string: str) -> Path:
    """Generate QR PNG image from string."""
    tmp_path = Path(tempfile.mktemp(suffix=".png"))
    try:
        subprocess.run(
            ["qrencode", "-o", str(tmp_path), "-s", "10", qr_string],
            check=True,
            capture_output=True
        )
        return tmp_path
    except subprocess.CalledProcessError as e:
        log(f"qrencode error: {e.stderr.decode()}")
        raise


def send_telegram_photo(chat_id: str, photo_path: Path, caption: str = "") -> bool:
    """Send photo to Telegram via Bot API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    try:
        with open(photo_path, "rb") as f:
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML"
            }
            files = {"photo": f}

            # Use multipart form upload
            import urllib.request
            import multipart

            # Simpler: use curl subprocess
            cmd = [
                "curl", "-s", "-X", "POST",
                url,
                "-F", f"chat_id={chat_id}",
                "-F", f"photo=@{photo_path}",
                "-F", f"caption={caption}",
                "-F", "parse_mode=HTML"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            resp = json.loads(result.stdout)

            if resp.get("ok"):
                log(f"Photo sent to chat {chat_id}")
                return True
            else:
                log(f"Telegram error: {resp.get('description', 'unknown')}")
                return False

    except Exception as e:
        log(f"Error sending photo: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="WhatsApp QR Notifier")
    parser.add_argument("--chat-id", default=DEFAULT_CHAT_ID, help="Telegram chat ID")
    parser.add_argument("--account", default="default", help="WhatsApp account ID")
    parser.add_argument("--dry-run", action="store_true", help="Test without sending")
    args = parser.parse_args()

    if not TELEGRAM_BOT_TOKEN:
        log("Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    if not args.chat_id:
        log("Error: No chat_id provided. Use --chat-id or set TELEGRAM_CHAT_ID")
        log("To get your chat_id, message the bot then run:")
        log(f"  curl -s 'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN[:20]}.../getUpdates?limit=1'")
        sys.exit(1)

    # Fetch QR status
    qr_data = fetch_qr(args.account)
    if "error" in qr_data:
        log(f"Failed to fetch QR: {qr_data['error']}")
        sys.exit(1)

    status = qr_data.get("status", "")
    qr_code = qr_data.get("qrCode", "")

    log(f"Account {args.account}: status={status}")

    if status != "qr_pending" or not qr_code:
        log("No QR pending, account may be connected")
        sys.exit(0)

    # Check if QR changed
    state = load_state()
    if not qr_changed(qr_code, state):
        log("QR unchanged, skipping")
        sys.exit(0)

    # Generate QR image
    log("Generating QR image...")
    qr_image = generate_qr_image(qr_code)

    caption = (
        f"📱 <b>WhatsApp QR Code</b>\n"
        f"Account: <code>{args.account}</code>\n"
        f"Status: {status}\n\n"
        f"Scan this QR with WhatsApp:\n"
        f"1. Open WhatsApp on your phone\n"
        f"2. Settings → Linked Devices → Link a Device\n"
        f"3. Scan this QR code"
    )

    if args.dry_run:
        log(f"Dry run: would send to {args.chat_id}")
        log(f"QR image saved: {qr_image}")
        print(f"Caption:\n{caption}")
        sys.exit(0)

    # Send to Telegram
    success = send_telegram_photo(args.chat_id, qr_image, caption)

    # Cleanup
    if qr_image.exists():
        qr_image.unlink()

    if success:
        save_state(qr_code)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()