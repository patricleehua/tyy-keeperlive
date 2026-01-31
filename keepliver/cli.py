#!/usr/bin/env python3
import argparse
import os
import sys
from typing import List


def _run_module_main(module, argv: List[str]) -> None:
    old_argv = sys.argv
    try:
        sys.argv = argv
        module.main()
    finally:
        sys.argv = old_argv


def _add_if(args: List[str], flag: str, value) -> None:
    if value is None:
        return
    args.extend([flag, str(value)])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified CLI for keepliver.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    login = sub.add_parser("login", help="Capture auth/device info for keepalive.")
    login.add_argument(
        "--backend",
        choices=["selenium", "playwright"],
        default="selenium",
        help="Browser automation backend.",
    )
    login.add_argument("--profile-dir", default=None, help="Persistent profile dir.")
    login.add_argument("--timeout", type=int, default=None, help="Wait timeout seconds.")
    login.add_argument("--out", default=None, help="Output config path.")
    login.add_argument("--chromedriver", default=None, help="Path to chromedriver.")
    login.add_argument("--chrome-binary", default=None, help="Path to Chrome binary.")
    login.add_argument("--edgedriver", default=None, help="Path to msedgedriver.")
    login.add_argument("--edge-binary", default=None, help="Path to Edge binary.")
    login.add_argument(
        "--browser",
        choices=["chrome", "edge"],
        default=None,
        help="Browser type for selenium (default: chrome).",
    )
    login.add_argument("--auto-connect", action="store_true", help="Auto-click Connect.")
    login.add_argument(
        "--login-mode",
        choices=["qr", "account"],
        default=None,
        help="Login mode for selenium (qr or account).",
    )
    login.add_argument("--account", default=None, help="Account/phone/email for login.")
    login.add_argument("--password", default=None, help="Password for login.")
    login.add_argument("--secrets", default=None, help="Path to secrets.json.")
    login.add_argument(
        "--headless",
        action="store_true",
        help="Headless mode (selenium: after first login; playwright: always).",
    )
    login.add_argument(
        "--force-headless",
        action="store_true",
        help="Force headless for selenium even if profile is new.",
    )
    login.add_argument(
        "--captcha-mode",
        choices=["auto", "manual", "off"],
        default=None,
        help="Captcha mode for selenium (auto/manual/off).",
    )
    login.add_argument(
        "--captcha-timeout",
        type=int,
        default=None,
        help="Captcha wait seconds.",
    )
    login.add_argument(
        "--captcha-port",
        type=int,
        default=None,
        help="Captcha web port (0 = console).",
    )
    login.add_argument(
        "--phone-verify-template",
        default=None,
        help="HTML template for phone verify input page.",
    )
    login.add_argument("--telegram-token", default=None, help="Telegram bot token.")
    login.add_argument("--telegram-chat-id", default=None, help="Telegram chat id.")
    login.add_argument(
        "--telegram-timeout",
        type=int,
        default=None,
        help="Seconds to wait for Telegram reply.",
    )
    login.add_argument(
        "--telegram-test",
        action="store_true",
        help="Send a startup test message to verify Telegram config.",
    )

    keepalive = sub.add_parser("keepalive", help="Run keepalive loop.")
    keepalive.add_argument("--config", default=None, help="Path to config.json.")
    keepalive.add_argument("--interval", type=int, default=None, help="Seconds between requests.")
    keepalive.add_argument("--once", action="store_true", help="Send once and exit.")

    once = sub.add_parser("once", help="Send one keepalive request and exit.")
    once.add_argument("--config", default=None, help="Path to config.json.")

    return parser


def main() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.insert(0, root)

    parser = build_parser()
    args = parser.parse_args()

    if args.cmd == "login":
        if args.backend == "playwright":
            from keepliver import ctyun_auto as mod

            argv = ["ctyun_auto.py"]
            _add_if(argv, "--profile-dir", args.profile_dir)
            _add_if(argv, "--timeout", args.timeout)
            _add_if(argv, "--out", args.out)
            if args.headless:
                argv.append("--headless")
            _run_module_main(mod, argv)
            return

        from keepliver import ctyun_auto_selenium as mod

        argv = ["ctyun_auto_selenium.py"]
        _add_if(argv, "--profile-dir", args.profile_dir)
        _add_if(argv, "--chromedriver", args.chromedriver)
        _add_if(argv, "--chrome-binary", args.chrome_binary)
        _add_if(argv, "--edgedriver", args.edgedriver)
        _add_if(argv, "--edge-binary", args.edge_binary)
        _add_if(argv, "--browser", args.browser)
        _add_if(argv, "--timeout", args.timeout)
        _add_if(argv, "--out", args.out)
        _add_if(argv, "--login-mode", args.login_mode)
        _add_if(argv, "--account", args.account)
        _add_if(argv, "--password", args.password)
        _add_if(argv, "--secrets", args.secrets)
        _add_if(argv, "--captcha-mode", args.captcha_mode)
        _add_if(argv, "--captcha-timeout", args.captcha_timeout)
        _add_if(argv, "--captcha-port", args.captcha_port)
        _add_if(argv, "--phone-verify-template", args.phone_verify_template)
        _add_if(argv, "--telegram-token", args.telegram_token)
        _add_if(argv, "--telegram-chat-id", args.telegram_chat_id)
        _add_if(argv, "--telegram-timeout", args.telegram_timeout)
        if args.telegram_test:
            argv.append("--telegram-test")
        if args.headless:
            argv.append("--headless")
        if args.force_headless:
            argv.append("--force-headless")
        if args.auto_connect:
            argv.append("--auto-connect")
        _run_module_main(mod, argv)
        return

    if args.cmd in ("keepalive", "once"):
        from keepliver import keepalive as mod

        argv = ["keepalive.py"]
        _add_if(argv, "--config", args.config)
        if args.cmd == "keepalive":
            _add_if(argv, "--interval", args.interval)
        if args.cmd == "once" or args.once:
            argv.append("--once")
        _run_module_main(mod, argv)
        return


if __name__ == "__main__":
    main()
