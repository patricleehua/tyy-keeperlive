#!/usr/bin/env python3
import argparse
import json
import os
import time


def _safe_json_loads(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Auto-capture CTYUN device_info + ctg headers + authData via Playwright."
    )
    parser.add_argument(
        "--profile-dir",
        default=os.path.join(os.path.dirname(__file__), ".pw-profile"),
        help="Persistent browser profile dir (keeps login).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (not recommended for first login).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Max seconds to wait for connect request.",
    )
    parser.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(__file__), "config.json"),
        help="Output config path.",
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print("Playwright not installed. Run: pip install playwright")
        print("Then run: playwright install")
        raise

    device_info_holder = {"value": None}
    headers_holder = {"value": None}

    def capture_request(request):
        url = request.url or ""
        if "/api/desktop/client/connect" in url and request.method == "POST":
            headers = request.headers
            ctg_headers = {k: v for k, v in headers.items() if k.lower().startswith("ctg-")}
            headers_holder["value"] = {
                "url": url,
                "ctg_headers": ctg_headers,
            }

    hook_js = """
(() => {
  const keys = [
    "objId","objType","osType","deviceId","deviceCode",
    "deviceName","sysVersion","appVersion","hostName",
    "vdCommand","ipAddress","macAddress","hardwareFeatureCode"
  ];
  const origStringify = JSON.stringify;
  JSON.stringify = function (value, ...rest) {
    try {
      if (value && typeof value === "object") {
        const hit = keys.every(k => k in value);
        if (hit) {
          window.__ctyun_device_info = value;
        }
      }
    } catch (e) {}
    return origStringify.apply(this, arguments);
  };
})();
"""

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            args.profile_dir,
            headless=args.headless,
        )
        page = context.new_page()
        page.on("request", capture_request)
        page.add_init_script(hook_js)
        page.goto("https://pc.ctyun.cn", wait_until="domcontentloaded")

        print("Waiting for login/localStorage authData... (please login if needed)")
        auth_data = None
        start = time.time()
        while time.time() - start < args.timeout:
            auth_text = page.evaluate("localStorage.getItem('authData')")
            if auth_text:
                auth_data = _safe_json_loads(auth_text)
                if auth_data:
                    break
            time.sleep(1)

        if not auth_data:
            print("authData not found. Login may not be complete.")
            print("Keep the browser open and try again.")
            context.close()
            return

        print("authData found. Now click Connect in the page to capture device_info...")
        device_info = None
        start = time.time()
        while time.time() - start < args.timeout:
            device_info = page.evaluate("window.__ctyun_device_info || null")
            if device_info:
                device_info_holder["value"] = device_info
            if device_info_holder["value"] and headers_holder["value"]:
                break
            time.sleep(0.5)

        if not device_info_holder["value"]:
            print("device_info not captured. Please click Connect and retry.")
            context.close()
            return
        if not headers_holder["value"]:
            print("ctg headers not captured. Please click Connect and retry.")
            context.close()
            return

        output = {
            "connect_url": headers_holder["value"]["url"],
            "ctg_headers": headers_holder["value"]["ctg_headers"],
            "device_info": device_info_holder["value"],
            "auth": {
                "userId": auth_data.get("userId"),
                "tenantId": auth_data.get("tenantId"),
                "secretKey": auth_data.get("secretKey"),
                "userAccount": auth_data.get("userAccount"),
            },
        }

        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=True, indent=2)
        print(f"Saved: {args.out}")

        context.close()


if __name__ == "__main__":
    main()
