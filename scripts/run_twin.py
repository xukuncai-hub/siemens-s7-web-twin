#!/usr/bin/env python3
"""One-command launcher for a TIA Web Twin project.

Starts the static page server and the S7comm gateway, then opens the page with
auto-connect enabled. Use --mock for a no-PLC demo.

  python run_twin.py --mock
  python run_twin.py --plc-ip 192.168.0.50 --rack 0 --slot 1
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="启动 TIA Web Twin（网页 + 网关 + 自动连接）")
    ap.add_argument("--mock", action="store_true", help="不连 PLC，网关使用 mock 后端")
    ap.add_argument("--config", default="gateway.config.json")
    ap.add_argument("--http-port", type=int, default=8000)
    ap.add_argument("--ws-port", type=int, default=8765)
    ap.add_argument("--bind", default="127.0.0.1", help="HTTP 与 WS 的监听地址")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--log-level", default="info")
    args = ap.parse_args()

    index = ROOT / "index.html"
    gateway = ROOT / "tia_gateway.py"
    manifest = ROOT / "twin.manifest.json"
    if not index.exists() or not manifest.exists() or (not args.mock and not gateway.exists()):
        print("项目不完整：请在生成的项目根目录运行（需要 index.html / twin.manifest.json；真实模式还需要 tia_gateway.py）")
        print(f"当前目录：{ROOT}")
        return 2

    http_port = free_port(args.http_port)
    ws_port = free_port(args.ws_port)
    handler = partial(QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer((args.bind, http_port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    gw_cmd = [
        sys.executable, str(gateway),
        "--config", str(ROOT / args.config),
        "--host", args.bind,
        "--port", str(ws_port),
        "--log-level", args.log_level,
    ]
    if args.mock:
        gw_cmd.append("--mock")
    else:
        gw_cmd.append("--wait-plc")

    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    proc = None
    try:
        if args.mock:
            page = f"http://127.0.0.1:{http_port}/"
            mode = "离线模式（网页内置，不启动网关）"
        else:
            print("正在启动网关…", flush=True)
            proc = subprocess.Popen(gw_cmd, cwd=str(ROOT), env=env)
            time.sleep(0.9)
            if proc.poll() is not None:
                print("网关启动失败。请检查上方错误；确认已 pip install -r requirements.txt。")
                return 1
            ws_url = f"ws://127.0.0.1:{ws_port}/ws"
            page = f"http://127.0.0.1:{http_port}/?ws={urllib.parse.quote(ws_url, safe='')}"
            mode = "网关就绪（页面默认离线，可输入 PLC 地址连接）"
        print("", flush=True)
        print("  TIA Web Twin 已启动", flush=True)
        print(f"  模式 : {mode}", flush=True)
        print(f"  页面 : {page}", flush=True)
        print("  页面默认离线仿真；切到“连接 PLC”输入地址即可。", flush=True)
        print("  停止 : Ctrl+C", flush=True)
        print("", flush=True)
        if not args.no_browser:
            threading.Timer(0.4, lambda: webbrowser.open(page)).start()
        while True:
            if proc is not None and proc.poll() is not None:
                print(f"网关已退出（code {proc.returncode}）。")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n正在停止…", flush=True)
    finally:
        server.shutdown()
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
