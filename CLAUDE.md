# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**tyy-keeperlive** is a CTYUN (China Telecom Cloud) automated login and device authentication tool using Selenium WebDriver. It captures authentication credentials, device info, and session headers needed for cloud desktop connections.

## Architecture

### Core Components

- **ctyun_auto_selenium.py**: Main automation script that drives Chrome via Selenium to:
  - Automate CTYUN login (QR code or account/password modes)
  - Handle CAPTCHA verification (OCR auto-recognition or manual input)
  - Manage phone verification dialogs with image and SMS codes
  - Inject JavaScript hooks to intercept device_info before encryption
  - Parse Chrome performance logs to capture network request headers
  - Output captured auth data to config.json

- **Captcha Handling**: Multi-mode system supporting:
  - `auto`: ddddocr library for OCR recognition
  - `manual`: HTTP server (default port 8000) serving web UI for manual input
  - `off`: Skip captcha handling

- **Phone Verification**: Two-step verification flow:
  - Captures image captcha from device binding dialog
  - Submits image code to trigger SMS
  - Collects SMS verification code via web UI or Telegram bot
  - Supports custom HTML templates via `--phone-verify-template`

- **Telegram Integration**: Optional bot support for receiving SMS codes remotely, useful for headless/server deployments

- **Profile Persistence**: Chrome user data directory (`.selenium-profile/`) maintains login sessions across runs, enabling headless mode after initial login

### Authentication Flow

1. Navigate to https://pc.ctyun.cn
2. Inject JavaScript hook to capture device_info object
3. Login via QR scan or account credentials
4. Handle CAPTCHA if present (OCR or manual)
5. Handle phone verification dialog if triggered
6. Wait for authData in localStorage
7. Auto-click "Connect" button (if `--auto-connect`)
8. Capture device_info from injected hook
9. Parse performance logs for ctg-* headers from /api/desktop/client/connect
10. Save all captured data to config.json

## Common Commands

### Run the main automation script
```bash
# First-time login with GUI (required for profile initialization)
python keepliver/ctyun_auto_selenium.py --login-mode account --secrets keepliver/secrets.json

# Subsequent runs in headless mode
python keepliver/ctyun_auto_selenium.py --headless --auto-connect --secrets keepliver/secrets.json

# With custom chromedriver path (Windows)
python keepliver/ctyun_auto_selenium.py --chromedriver keepliver/chromedriver.exe

# With Telegram bot for SMS codes
python keepliver/ctyun_auto_selenium.py --telegram-token "YOUR_BOT_TOKEN" --telegram-chat-id "YOUR_CHAT_ID"

# Console input mode (no web server)
python keepliver/ctyun_auto_selenium.py --captcha-port 0
```

### secrets.json format
```json
{
  "account": "your_account",
  "password": "your_password",
  "telegram_token": "optional_bot_token",
  "telegram_chat_id": "optional_chat_id"
}
```

## Key Implementation Details

### JavaScript Hook Injection
The script injects `HOOK_JS` that intercepts `JSON.stringify` calls to capture the device_info object before it gets encrypted and sent to the server. This object contains critical device identification fields.

### Performance Log Parsing
Chrome DevTools Protocol performance logs are continuously parsed to extract:
- Connect request URL
- ctg-* prefixed headers (authentication headers)
- Response status for SMS code requests

### Headless Mode Safety
Headless mode is only enabled if the profile directory is initialized (contains "Default", "Profile 1", or "Local State"). This prevents QR code login issues on first run.

### HTTP Servers for Manual Input
Two temporary HTTP servers can spin up on-demand:
- Captcha server: Single image code input
- Phone verify server: Image + SMS code input (supports custom HTML templates)

Both servers run in daemon threads and auto-shutdown after receiving input or timeout.

## Project Structure

```
keepliver/
├── ctyun_auto_selenium.py  # Main Selenium automation (1000+ lines)
├── ctyun_auto.py           # Alternative implementation
├── keepalive.py            # Keep-alive functionality
├── cli.py                  # Command-line interface
├── chromedriver.exe        # Windows ChromeDriver binary
├── secrets.json            # Credentials (gitignored)
├── .selenium-profile/      # Chrome user data directory
└── html/                   # HTML templates for verification pages
```

## Dependencies

- **selenium**: Browser automation framework
- **ddddocr**: OCR library for captcha recognition (using DdddOcr class)
- **Pillow**: Image processing (indirect dependency of ddddocr)

Install with: `uv sync` or `pip install -e .`
