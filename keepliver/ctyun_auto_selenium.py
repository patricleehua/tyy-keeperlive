#!/usr/bin/env python3
import argparse
import base64
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from queue import Queue
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlencode
from urllib.request import Request, urlopen

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def _safe_json_loads(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


_PERFLOG_WARNED = False


def _get_performance_logs(driver):
    global _PERFLOG_WARNED
    try:
        log_types = getattr(driver, "log_types", None)
        if log_types is not None and "performance" not in log_types:
            if not _PERFLOG_WARNED:
                print("Performance logs unavailable; skipping network capture.")
                _PERFLOG_WARNED = True
            return []
    except Exception:
        pass
    try:
        return driver.get_log("performance")
    except Exception:
        if not _PERFLOG_WARNED:
            print("Performance logs unavailable; skipping network capture.")
            _PERFLOG_WARNED = True
        return []


def _safe_load_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _try_ocr_captcha(image_path: str) -> Optional[str]:
    try:
        from PIL import Image

        if not hasattr(Image, "ANTIALIAS") and hasattr(Image, "Resampling"):
            Image.ANTIALIAS = Image.Resampling.LANCZOS
    except Exception:
        pass

    try:
        import ddddocr
    except Exception as e:
        ddddocr = None
        print(f"导入ddddocr失败: {e}") 
    try:
        with open(image_path, "rb") as f:
            data = f.read()
        if ddddocr is not None:
            ocr = ddddocr.DdddOcr(show_ad=False)
            code = ocr.classification(data)
        else:
            return None
        if code:
            return str(code).strip()
    except Exception as exc:
        print(f"OCR failed: {exc!r}")
        return None
    return None


def _tg_request(url: str, data: Optional[bytes] = None, timeout: int = 10) -> Optional[dict]:
    try:
        req = Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
        return _safe_json_loads(payload) or None
    except Exception:
        return None


def _tg_send_message(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    resp = _tg_request(url, data=data, timeout=10)
    return bool(resp and resp.get("ok"))


def _tg_get_latest_offset(token: str) -> Optional[int]:
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    data = urlencode({"limit": 1, "timeout": 1}).encode("utf-8")
    resp = _tg_request(url, data=data, timeout=10)
    if not resp or not resp.get("ok"):
        return None
    results = resp.get("result") or []
    if not results:
        return None
    latest = results[-1].get("update_id")
    if isinstance(latest, int):
        return latest + 1
    return None


def _tg_wait_for_code(
    token: str, chat_id: str, timeout: int, offset: Optional[int]
) -> Tuple[Optional[str], Optional[int]]:
    end = time.time() + timeout
    last_offset = offset
    while time.time() < end:
        params = {"timeout": 20}
        if last_offset is not None:
            params["offset"] = last_offset
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        data = urlencode(params).encode("utf-8")
        resp = _tg_request(url, data=data, timeout=30)
        if not resp or not resp.get("ok"):
            time.sleep(1)
            continue
        results = resp.get("result") or []
        for upd in results:
            update_id = upd.get("update_id")
            if isinstance(update_id, int):
                last_offset = update_id + 1
            msg = upd.get("message") or upd.get("edited_message") or {}
            chat = msg.get("chat") or {}
            if str(chat.get("id")) != str(chat_id):
                continue
            text = (msg.get("text") or "").strip()
            if text:
                return text, last_offset
        time.sleep(0.5)
    return None, last_offset


def _resolve_driver_path(path: str, exe_base: str) -> str:
    if os.path.isdir(path):
        exe_name = f"{exe_base}.exe" if os.name == "nt" else exe_base
        path = os.path.join(path, exe_name)
    if os.path.exists(path):
        path = os.path.abspath(path)
    return path


def _start_captcha_server(image_b64: str, port: int, queue: Queue) -> HTTPServer:
    html = f"""<html><head><meta charset="utf-8"><title>CTYUN Captcha</title></head>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<body>
<h3>请输入验证码</h3>
<form method="POST" action="/submit">
  <input type="text" name="code" maxlength="8" size="8"/>
  <input type="submit" value="提交"/>
</form>
<p><img src="data:image/png;base64,{image_b64}" /></p>
</body></html>"""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            params = parse_qs(body)
            code = params.get("code", [""])[0].strip()
            if not code:
                code = params.get("img_code", [""])[0].strip()
            if not code:
                code = params.get("sms_code", [""])[0].strip()
            if code:
                queue.put(code)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, *_args, **_kwargs):
            return

    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
    except OSError:
        if port == 0:
            raise
        server = HTTPServer(("0.0.0.0", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _render_phone_verify_html(
    template_path: str, image_b64: str, sms_only: bool
) -> str:
    if sms_only:
        default_fields = (
            '<div>短信验证码: <input type="text" name="sms_code" maxlength="8" size="8"/></div>'
        )
    else:
        default_fields = (
            '<div>图形验证码: <input type="text" name="img_code" maxlength="8" size="8"/></div>'
            '<div>短信验证码: <input type="text" name="sms_code" maxlength="8" size="8"/></div>'
        )
    default_html = f"""<html><head><meta charset="utf-8"><title>CTYUN Verify</title></head>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<body>
<h3>手机号验证</h3>
<p>请输入图形验证码并获取短信验证码，再填写短信验证码。</p>
<form method="POST" action="/submit">
  {default_fields}
  <input type="submit" value="提交"/>
</form>
<p><img src="data:image/png;base64,{image_b64}" /></p>
</body></html>"""

    if not template_path or not os.path.exists(template_path):
        return default_html
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            tpl = f.read()
    except Exception:
        return default_html

    html = tpl
    if "{{IMAGE_DATA}}" in html:
        html = html.replace("{{IMAGE_DATA}}", image_b64)
    else:
        html = html.replace(
            '{{ url_for(\'static\', filename=\'ctyun.png\') }}',
            f"data:image/png;base64,{image_b64}",
        )
        html = html.replace(
            "{{ url_for('static', filename='ctyun.png') }}",
            f"data:image/png;base64,{image_b64}",
        )
    has_img = "img_code" in html
    has_sms = "sms_code" in html
    has_code = "name='code'" in html or 'name="code"' in html

    if "{{FORM_FIELDS}}" in html:
        html = html.replace("{{FORM_FIELDS}}", default_fields)
        return html

    if has_code:
        if sms_only:
            html = html.replace("name='code'", "name='sms_code'")
            html = html.replace('name="code"', 'name="sms_code"')
            has_sms = True
        else:
            html = html.replace("name='code'", "name='img_code'")
            html = html.replace('name="code"', 'name="img_code"')
            has_img = True

    if sms_only:
        if not has_sms and "</form>" in html:
            html = html.replace("</form>", f"{default_fields}</form>")
    else:
        if (not has_img or not has_sms) and "</form>" in html:
            if not has_img:
                html = html.replace(
                    "</form>",
                    '<div>图形验证码: <input type="text" name="img_code" maxlength="8" size="8"/></div></form>',
                )
            if not has_sms:
                html = html.replace(
                    "</form>",
                    '<div>短信验证码: <input type="text" name="sms_code" maxlength="8" size="8"/></div></form>',
                )
    if "action='/ctyuncode'" in html:
        html = html.replace("action='/ctyuncode'", "action='/submit'")
    if "action=\"/ctyuncode\"" in html:
        html = html.replace("action=\"/ctyuncode\"", "action=\"/submit\"")
    return html


def _start_phone_verify_server(
    image_b64: str, port: int, queue: Queue, template_path: str, sms_only: bool
) -> HTTPServer:
    html = _render_phone_verify_html(template_path, image_b64, sms_only)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            params = parse_qs(body)
            img_code = params.get("img_code", [""])[0].strip()
            sms_code = params.get("sms_code", [""])[0].strip()
            if not img_code and not sms_code:
                code = params.get("code", [""])[0].strip()
                if code:
                    if sms_only:
                        sms_code = code
                    else:
                        img_code = code
            if img_code or sms_code:
                queue.put({"img_code": img_code, "sms_code": sms_code})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, *_args, **_kwargs):
            return

    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
    except OSError:
        if port == 0:
            raise
        server = HTTPServer(("0.0.0.0", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _is_profile_initialized(profile_dir: str) -> bool:
    if not profile_dir:
        return False
    if not os.path.isdir(profile_dir):
        return False
    entries = set(os.listdir(profile_dir))
    if "Default" in entries or "Profile 1" in entries:
        return True
    if "Local State" in entries:
        return True
    return False


def _resolve_account_password(args) -> Tuple[Optional[str], Optional[str]]:
    if args.account and args.password:
        return args.account, args.password
    if args.secrets:
        data = _safe_load_json(args.secrets)
        if isinstance(data, dict):
            account = args.account or data.get("account")
            password = args.password or data.get("password")
            return account, password
    return args.account, args.password


def _resolve_telegram_config(args) -> Tuple[Optional[str], Optional[str]]:
    token = args.telegram_token or ""
    chat_id = args.telegram_chat_id or ""
    if token and chat_id:
        return token, chat_id
    if args.secrets:
        data = _safe_load_json(args.secrets)
        if isinstance(data, dict):
            token = token or data.get("telegram_token") or data.get("tg_token")
            chat_id = chat_id or data.get("telegram_chat_id") or data.get("tg_chat_id")
    return token or None, chat_id or None


def _try_click_by_text(driver, texts):
    try:
        driver.execute_script(
            """
            const texts = arguments[0];
            const nodes = Array.from(document.querySelectorAll('button, a, div, span'));
            const el = nodes.find(n => texts.includes((n.innerText || '').trim()));
            if (el) { el.click(); return true; }
            return false;
            """,
            texts,
        )
        return True
    except Exception:
        return False


def _ensure_account_login_view(driver):
    # Try to switch from QR login to account/password login.
    candidates = ["账号登录", "密码登录", "账户登录", "账号登陆"]
    _try_click_by_text(driver, candidates)
    time.sleep(0.5)
    try:
        driver.execute_script(
            """
            const right = document.querySelector('.right');
            if (right) {
              right.classList.remove('hide');
              right.style.display = 'block';
              right.style.visibility = 'visible';
              right.style.opacity = '1';
            }
            const qr = document.querySelector('.qr-code');
            if (qr) { qr.style.display = 'none'; }
            """
        )
    except Exception:
        pass


def _fill_account_password(driver, account: str, password: str) -> bool:
    try:
        account_input = driver.find_element(By.CSS_SELECTOR, "input.account")
        password_input = driver.find_element(By.CSS_SELECTOR, "input.password")
    except Exception:
        # Fallback: set via JS and dispatch events
        try:
            ok = driver.execute_script(
                """
                const acct = document.querySelector('input.account');
                const pwd = document.querySelector('input.password');
                if (!acct || !pwd) return false;
                const setVal = (el, v) => {
                  el.focus();
                  el.value = v;
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                };
                setVal(acct, arguments[0]);
                setVal(pwd, arguments[1]);
                return true;
                """,
                account,
                password,
            )
            if ok:
                return True
        except Exception:
            return False
        return False

    account_input.clear()
    account_input.send_keys(account)
    password_input.clear()
    password_input.send_keys(password)

    # Agree terms if checkbox exists and not checked
    try:
        checkbox = driver.find_element(By.CSS_SELECTOR, "input.el-checkbox__original")
        if not checkbox.is_selected():
            checkbox.click()
    except Exception:
        pass
    return True


def _submit_login(driver):
    # Prefer explicit submit button in account login
    try:
        btn = driver.find_element(By.CSS_SELECTOR, ".btn-submit, .btn-submit-pc")
        btn.click()
        return True
    except Exception:
        try:
            ok = driver.execute_script(
                """
                const btn = document.querySelector('.btn-submit-pc') || document.querySelector('.btn-submit');
                if (btn) { btn.click(); return true; }
                return false;
                """
            )
            if ok:
                return True
        except Exception:
            pass
        return _try_click_by_text(driver, ["登录", "安全登录"])


def _fetch_blob_image_b64(driver, img_selector: str) -> Optional[str]:
    try:
        return driver.execute_async_script(
            """
            const sel = arguments[0];
            const cb = arguments[arguments.length - 1];
            const img = document.querySelector(sel);
            if (!img || !img.src || !img.src.startsWith('blob:')) { cb(null); return; }
            fetch(img.src).then(r => r.blob()).then(b => {
              const reader = new FileReader();
              reader.onloadend = () => cb(reader.result);
              reader.readAsDataURL(b);
            }).catch(() => cb(null));
            """,
            img_selector,
        )
    except Exception:
        return None


def _handle_phone_verify_dialog(driver, args) -> bool:
    # Returns True if dialog handled (or attempted)
    try:
        dialog = driver.find_element(By.CSS_SELECTOR, "#dialog-deviceBind")
    except Exception:
        if PHONE_VERIFY_STATE["completed"] or PHONE_VERIFY_STATE["in_progress"]:
            PHONE_VERIFY_STATE["completed"] = False
            PHONE_VERIFY_STATE["in_progress"] = False
        return False
    if PHONE_VERIFY_STATE["completed"] or PHONE_VERIFY_STATE["in_progress"]:
        return True
    PHONE_VERIFY_STATE["in_progress"] = True

    try:
        img_data_url = _fetch_blob_image_b64(driver, "#dialog-deviceBind img.img")
        if not img_data_url:
            PHONE_VERIFY_STATE["in_progress"] = False
            return True
        image_b64 = img_data_url.split(",", 1)[-1]
        img_code = None
        sms_code = ""
        img_code_from_ocr = False
        if args.captcha_mode == "auto":
            cap_path = os.path.join(os.path.dirname(__file__), "captcha_bind.png")
            with open(cap_path, "wb") as f:
                f.write(base64.b64decode(image_b64))
            print("Running OCR for phone-verify image...")
            img_code = _try_ocr_captcha(cap_path)
            if img_code:
                print(f"OCR img code: {img_code}")
                img_code_from_ocr = True

        if not img_code:
            if args.captcha_port == 0:
                img_code = input("请输入图形验证码: ").strip()
            else:
                q = Queue()
                server = _start_phone_verify_server(
                    image_b64, args.captcha_port, q, args.phone_verify_template, False
                )
                print(f"Phone verify page: http://127.0.0.1:{server.server_port}/")
                try:
                    payload = q.get(timeout=args.captcha_timeout)
                    img_code = payload.get("img_code", "").strip()
                    sms_code = payload.get("sms_code", "").strip()
                except Exception:
                    img_code = None
                    sms_code = ""
                finally:
                    server.shutdown()
        else:
            sms_code = ""

        if img_code:
            try:
                driver.execute_script(
                    """
                    const inp = document.querySelector('#dialog-deviceBind input[placeholder="请输入图形验证码"]');
                    if (!inp) return;
                    inp.focus();
                    inp.value = arguments[0];
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                    inp.dispatchEvent(new Event('keyup', { bubbles: true }));
                    inp.dispatchEvent(new Event('blur', { bubbles: true }));
                    """,
                    img_code,
                )
                # Click "获取验证码" to send SMS
                time.sleep(0.3)
                driver.execute_script(
                    """
                    const btn = document.querySelector('#dialog-deviceBind .box-form-item-sms');
                    if (btn) {
                      btn.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
                      btn.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
                      btn.click();
                      btn.dispatchEvent(new MouseEvent('click', {bubbles:true}));
                    }
                    """
                )
                if img_code_from_ocr and args.captcha_port != 0:
                    print(f"OCR code: {img_code}")
                    print("OCR ok; please enter SMS code only.")
            except Exception:
                pass

        # Try to surface toast/error messages
        try:
            msg = driver.execute_script(
                """
                const el = document.querySelector('.el-message__content');
                return el ? el.innerText : '';
                """
            )
            if msg:
                print(f"CTYUN message: {msg}")
        except Exception:
            pass
        try:
            form_err = driver.execute_script(
                """
                const el = document.querySelector('#dialog-deviceBind .el-form-item__error');
                return el ? el.innerText : '';
                """
            )
            if form_err:
                print(f"CTYUN form error: {form_err}")
        except Exception:
            pass

        # Inspect performance logs for getSmsCode response
        sms_sent = False
        try:
            time.sleep(1)
            logs = _get_performance_logs(driver)
            for entry in logs:
                try:
                    message = json.loads(entry["message"]).get("message", {})
                    if message.get("method") == "Network.responseReceived":
                        resp = message.get("params", {}).get("response", {})
                        url = resp.get("url", "")
                        if "/api/cdserv/client/device/getSmsCode" in url:
                            status = resp.get("status")
                            print(f"getSmsCode response: {status} {url}")
                            sms_sent = True
                except Exception:
                    continue
        except Exception:
            pass
        if not sms_sent:
            try:
                btn_text = driver.execute_script(
                    """
                    const btn = document.querySelector('#dialog-deviceBind .box-form-item-sms');
                    return btn ? (btn.innerText || '').trim() : '';
                    """
                )
                if btn_text and ("秒" in btn_text or "s" in btn_text):
                    sms_sent = True
                    print(f"SMS button state: {btn_text}")
            except Exception:
                pass
        if not sms_sent:
            print("SMS send not confirmed (no response/timeout).")

        if not sms_code:
            if args.captcha_port == 0:
                sms_code = input("请输入短信验证码: ").strip()
            else:
                if not sms_sent:
                    PHONE_VERIFY_STATE["in_progress"] = False
                    return True
                if args.telegram_token and args.telegram_chat_id:
                    if _tg_send_message(
                        args.telegram_token,
                        args.telegram_chat_id,
                        f"检测到需要短信验证码，请在 {args.telegram_timeout}s 内回复验证码（超时将提供输入地址）。",
                    ):
                        code, offset = _tg_wait_for_code(
                            args.telegram_token,
                            args.telegram_chat_id,
                            args.telegram_timeout,
                            args.telegram_offset,
                        )
                        args.telegram_offset = offset
                        sms_code = (code or "").strip()
                if not sms_code:
                    qsms = Queue()
                    server_sms = _start_phone_verify_server(
                        image_b64, args.captcha_port, qsms, args.phone_verify_template, True
                    )
                    local_url = f"http://127.0.0.1:{server_sms.server_port}/"
                    base_url = (args.captcha_base_url or "http://127.0.0.1").rstrip("/")
                    url = f"{base_url}:{server_sms.server_port}/"
                    print(f"SMS verify page: {local_url}")
                    if args.telegram_token and args.telegram_chat_id:
                        _tg_send_message(
                            args.telegram_token,
                            args.telegram_chat_id,
                            f"Telegram 等待验证码超时，请打开输入页：{url}",
                        )
                    try:
                        payload_sms = qsms.get(timeout=args.captcha_timeout)
                        sms_code = payload_sms.get("sms_code", "").strip()
                    except Exception:
                        sms_code = ""
                    finally:
                        server_sms.shutdown()

        if sms_code:
            try:
                driver.execute_script(
                    """
                    const inp = document.querySelector('#dialog-deviceBind input[placeholder="请输入短信验证码"]');
                    if (!inp) return;
                    inp.focus();
                    inp.value = arguments[0];
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                    """,
                    sms_code,
                )
            except Exception:
                pass

        try:
            driver.execute_script(
                """
                const btns = document.querySelectorAll('#dialog-deviceBind button.box-form-item-submit');
                if (btns && btns.length > 1) { btns[1].click(); return; }
                const ok = Array.from(btns).find(b => (b.innerText || '').trim() === '确定');
                if (ok) ok.click();
                """
            )
        except Exception:
            pass

        if sms_code:
            PHONE_VERIFY_STATE["completed"] = True
        else:
            print("SMS code not provided; phone verify not completed.")
        PHONE_VERIFY_STATE["in_progress"] = False
        return True
    except Exception:
        PHONE_VERIFY_STATE["in_progress"] = False
        return True


HOOK_JS = r"""
(() => {
  const CAPTURE_PATH = "/api/desktop/client/connect";
  const CTG_PREFIX = "ctg-";
  const capture = (url, method, headers) => {
    try {
      if (!url || !method) return;
      if (!url.includes(CAPTURE_PATH)) return;
      if (String(method).toUpperCase() !== "POST") return;
      const ctg = {};
      if (headers && typeof headers.forEach === "function") {
        headers.forEach((v, k) => {
          if (String(k).toLowerCase().startsWith(CTG_PREFIX)) {
            ctg[k] = v;
          }
        });
      } else if (headers && typeof headers === "object") {
        for (const k of Object.keys(headers)) {
          if (String(k).toLowerCase().startsWith(CTG_PREFIX)) {
            ctg[k] = headers[k];
          }
        }
      }
      if (Object.keys(ctg).length > 0) {
        window.__ctyun_connect_capture = { url, headers: ctg, ts: Date.now() };
      }
    } catch (e) {}
  };

  // Hook fetch
  try {
    const origFetch = window.fetch;
    if (origFetch) {
      window.fetch = function(input, init) {
        try {
          const req = input instanceof Request ? input : null;
          const url = req ? req.url : String(input || "");
          const method = (init && init.method) || (req && req.method) || "GET";
          const hdrs = new Headers();
          const h1 = req && req.headers ? req.headers : null;
          const h2 = init && init.headers ? init.headers : null;
          if (h1) new Headers(h1).forEach((v, k) => hdrs.set(k, v));
          if (h2) new Headers(h2).forEach((v, k) => hdrs.set(k, v));
          capture(url, method, hdrs);
        } catch (e) {}
        return origFetch.apply(this, arguments);
      };
    }
  } catch (e) {}

  // Hook XHR
  try {
    const origOpen = XMLHttpRequest.prototype.open;
    const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
    const origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url) {
      this.__ctyun_method = method;
      this.__ctyun_url = url;
      this.__ctyun_headers = {};
      return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.setRequestHeader = function(k, v) {
      try {
        this.__ctyun_headers = this.__ctyun_headers || {};
        this.__ctyun_headers[k] = v;
      } catch (e) {}
      return origSetHeader.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function() {
      try {
        const hdrs = new Headers(this.__ctyun_headers || {});
        capture(this.__ctyun_url, this.__ctyun_method, hdrs);
      } catch (e) {}
      return origSend.apply(this, arguments);
    };
  } catch (e) {}

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

PHONE_VERIFY_STATE = {
    "in_progress": False,
    "completed": False,
}


def main():
    parser = argparse.ArgumentParser(
        description="Auto-capture CTYUN device_info + ctg headers + authData via Selenium."
    )
    parser.add_argument(
        "--profile-dir",
        default=os.path.join(os.path.dirname(__file__), ".selenium-profile"),
        help="Persistent Chrome profile dir (keeps login).",
    )
    parser.add_argument(
        "--chromedriver",
        default="chromedriver",
        help="Path to chromedriver (in PATH or absolute).",
    )
    parser.add_argument(
        "--edgedriver",
        default="msedgedriver",
        help="Path to msedgedriver (in PATH or absolute).",
    )
    parser.add_argument(
        "--browser",
        choices=["chrome", "edge"],
        default="chrome",
        help="Browser type for selenium (default: chrome).",
    )
    parser.add_argument(
        "--chrome-binary",
        default="",
        help="Optional Chrome binary path.",
    )
    parser.add_argument(
        "--edge-binary",
        default="",
        help="Optional Edge binary path.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Max seconds to wait for connect request.",
    )
    parser.add_argument(
        "--auto-connect",
        action="store_true",
        help="Try to click the Connect button automatically.",
    )
    parser.add_argument(
        "--login-mode",
        choices=["qr", "account"],
        default="qr",
        help="Login mode: qr (scan) or account (username/password).",
    )
    parser.add_argument("--account", default="", help="Account/phone/email for login.")
    parser.add_argument("--password", default="", help="Password for login.")
    parser.add_argument(
        "--secrets",
        default="",
        help="Path to secrets.json with account/password.",
    )
    parser.add_argument(
        "--captcha-mode",
        choices=["auto", "manual", "off"],
        default="auto",
        help="Captcha mode: auto (OCR), manual (web/console), off (skip).",
    )
    parser.add_argument(
        "--captcha-timeout",
        type=int,
        default=120,
        help="Seconds to wait for captcha input.",
    )
    parser.add_argument(
        "--captcha-port",
        type=int,
        default=8000,
        help="Port for captcha web input (0 = console input).",
    )
    parser.add_argument(
        "--captcha-base-url",
        default="http://127.0.0.1",
        help="Base URL for captcha input page (used in Telegram messages).",
    )
    parser.add_argument(
        "--phone-verify-template",
        default=os.path.join(os.path.dirname(__file__), "login-phone-verify.html"),
        help="HTML template for phone verify input page.",
    )
    parser.add_argument(
        "--telegram-token",
        default="",
        help="Telegram bot token for SMS code prompt.",
    )
    parser.add_argument(
        "--telegram-chat-id",
        default="",
        help="Telegram chat id to receive/send SMS code.",
    )
    parser.add_argument(
        "--telegram-timeout",
        type=int,
        default=None,
        help="Seconds to wait for Telegram reply (defaults to captcha-timeout).",
    )
    parser.add_argument(
        "--telegram-test",
        action="store_true",
        help="Send a startup test message to verify Telegram config.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome in headless mode (recommended after first login).",
    )
    parser.add_argument(
        "--force-headless",
        action="store_true",
        help="Force headless even if profile is not initialized.",
    )
    parser.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(__file__), "config.json"),
        help="Output config path.",
    )
    args = parser.parse_args()
    if not args.telegram_timeout:
        args.telegram_timeout = args.captcha_timeout
    args.telegram_token, args.telegram_chat_id = _resolve_telegram_config(args)
    args.telegram_offset = None
    if args.telegram_token:
        args.telegram_offset = _tg_get_latest_offset(args.telegram_token)
        if args.telegram_test and args.telegram_chat_id:
            _tg_send_message(
                args.telegram_token,
                args.telegram_chat_id,
                "Telegram test: bot is configured successfully.",
            )

    if args.browser == "edge":
        caps = DesiredCapabilities.EDGE.copy()
    else:
        caps = DesiredCapabilities.CHROME.copy()
    caps["goog:loggingPrefs"] = {"performance": "ALL"}
    caps["ms:loggingPrefs"] = {"performance": "ALL"}

    if args.browser == "edge":
        options = EdgeOptions()
        options.use_chromium = True
    else:
        options = Options()
    options.add_argument(f"--user-data-dir={args.profile_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--remote-debugging-port=0")
    if os.name != "nt":
        options.add_argument("--disable-dev-shm-usage")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            options.add_argument("--no-sandbox")
    if args.headless:
        if _is_profile_initialized(args.profile_dir) or args.force_headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1280,720")
        else:
            print("Profile not initialized; ignoring --headless for first login.")
    options.set_capability("goog:loggingPrefs", caps.get("goog:loggingPrefs", {}))
    options.set_capability("ms:loggingPrefs", caps.get("ms:loggingPrefs", {}))
    if args.browser == "edge":
        if args.edge_binary:
            options.binary_location = args.edge_binary
        edgedriver_path = _resolve_driver_path(args.edgedriver, "msedgedriver")
        service = EdgeService(executable_path=edgedriver_path)
        driver = webdriver.Edge(service=service, options=options)
    else:
        if args.chrome_binary:
            options.binary_location = args.chrome_binary
        chromedriver_path = _resolve_driver_path(args.chromedriver, "chromedriver")
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get("https://pc.ctyun.cn")
        # Inject hook to capture device_info before encryption
        driver.execute_script(HOOK_JS)

        if args.login_mode == "account":
            account, password = _resolve_account_password(args)
            if not account or not password:
                print("Missing account/password. Provide --account/--password or --secrets.")
                return
            _ensure_account_login_view(driver)
            if _fill_account_password(driver, account, password):
                _submit_login(driver)

        print("Waiting for login/localStorage authData... (please login if needed)")
        auth_data = None
        start = time.time()
        last_captcha_try = 0.0
        while time.time() - start < args.timeout:
            _handle_phone_verify_dialog(driver, args)
            if args.captcha_mode != "off" and time.time() - last_captcha_try > 1.0:
                last_captcha_try = time.time()
                try:
                    code_input = driver.find_element(By.CSS_SELECTOR, ".code")
                    code_img = driver.find_element(By.CSS_SELECTOR, ".code-img")
                    if (code_input.get_attribute("value") or "") == "":
                        os.makedirs(os.path.dirname(__file__), exist_ok=True)
                        cap_path = os.path.join(os.path.dirname(__file__), "captcha.png")
                        code_img.screenshot(cap_path)
                        code = None
                        if args.captcha_mode == "auto":
                            print("Running OCR for login captcha...")
                            code = _try_ocr_captcha(cap_path)
                            if code:
                                print(f"OCR code: {code}")
                        if not code:
                            if args.captcha_port == 0:
                                code = input("请输入验证码: ").strip()
                            else:
                                with open(cap_path, "rb") as f:
                                    b64 = base64.b64encode(f.read()).decode("ascii")
                                q = Queue()
                                server = _start_captcha_server(b64, args.captcha_port, q)
                                print(
                                    f"Captcha page: http://127.0.0.1:{server.server_port}/"
                                )
                                try:
                                    code = q.get(timeout=args.captcha_timeout).strip()
                                except Exception:
                                    code = None
                                finally:
                                    server.shutdown()
                        if code:
                            code_input.clear()
                            code_input.send_keys(code)
                            _submit_login(driver)
                except Exception:
                    pass

            auth_text = driver.execute_script("return localStorage.getItem('authData')")
            if auth_text:
                auth_data = _safe_json_loads(auth_text)
                if auth_data:
                    break
            time.sleep(1)

        if not auth_data:
            print("authData not found. Login may not be complete.")
            print("Keep the browser open and try again.")
            return

        def try_auto_click():
            try:
                wait = WebDriverWait(driver, 10)
                el = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".desktopcom-enter"))
                )
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                return True
            except Exception:
                try:
                    driver.execute_script(
                        """
                        const texts = ['进入AI云电脑','连接云电脑','连接'];
                        const btns = Array.from(document.querySelectorAll('button, a, div'));
                        const el = btns.find(b => texts.includes(b.innerText?.trim()));
                        if (el) { el.click(); return true; }
                        return false;
                        """
                    )
                except Exception:
                    return False

        if args.auto_connect:
            print("authData found. Trying to auto-click Connect...")
            try_auto_click()
        else:
            print("authData found. Now click Connect in the page to capture device_info and headers...")

        device_info = None
        ctg_headers = None
        connect_url = None
        start = time.time()
        last_click = 0.0
        while time.time() - start < args.timeout:
            # Pull device_info captured by hook
            device_info = driver.execute_script("return window.__ctyun_device_info || null")
            if not ctg_headers or not connect_url:
                cap = driver.execute_script("return window.__ctyun_connect_capture || null")
                if cap and isinstance(cap, dict):
                    if not connect_url and cap.get("url"):
                        connect_url = cap.get("url")
                    if not ctg_headers and cap.get("headers"):
                        ctg_headers = cap.get("headers")

            # Parse performance logs to find connect request headers
            logs = _get_performance_logs(driver)
            for entry in logs:
                try:
                    message = json.loads(entry["message"])
                    msg = message.get("message", {})
                    if msg.get("method") == "Network.requestWillBeSent":
                        req = msg.get("params", {}).get("request", {})
                        url = req.get("url", "")
                        if "/api/desktop/client/connect" in url and req.get("method") == "POST":
                            connect_url = url
                            headers = req.get("headers", {})
                            ctg_headers = {k: v for k, v in headers.items() if k.lower().startswith("ctg-")}
                except Exception:
                    continue

            if device_info and ctg_headers and connect_url:
                break
            if args.auto_connect and time.time() - last_click > 5:
                if try_auto_click():
                    last_click = time.time()
            time.sleep(0.5)

        if not device_info:
            print("device_info not captured. Please click Connect and retry.")
            return
        if not ctg_headers:
            print("ctg headers not captured. Please click Connect and retry.")
            return

        output = {
            "connect_url": connect_url,
            "ctg_headers": ctg_headers,
            "device_info": device_info,
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
        print("Waiting 5 seconds before closing browser...")
        time.sleep(5)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
