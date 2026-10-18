#!/usr/bin/env python3
"""TIA Web Twin desktop shell.

A small double-clickable control window that serves the web page and runs the
same WebSocket/S7comm gateway in-process. It is the entry point for the
optional Windows one-file build (PyInstaller).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import tia_gateway as tg  # noqa: E402


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
    def log_message(self, *args):
        pass


class Runtime:
    def __init__(self):
        self.http_port = 0
        self.ws_port = 0
        self.httpd: ThreadingHTTPServer | None = None
        self.gw = None
        self.loop = None
        self.error = ""
        self.started = threading.Event()
        self.page_url = ""

    def start(self):
        self.http_port = free_port(8000)
        self.ws_port = free_port(8765)
        handler = partial(QuietHandler, directory=str(ROOT))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.http_port), handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        threading.Thread(target=self._gateway_thread, daemon=True).start()
        ws_url = f"ws://127.0.0.1:{self.ws_port}/ws"
        self.page_url = (f"http://127.0.0.1:{self.http_port}/?"
                         f"ws={urllib.parse.quote(ws_url, safe='')}")
        # The page starts offline; give the gateway a moment to bind before the
        # user can select "连接 PLC".
        time.sleep(0.6)
        if self.error:
            raise RuntimeError(self.error)

    def _gateway_thread(self):
        try:
            log_path = Path(tempfile.gettempdir()) / "tia-web-twin.log"
            logging.basicConfig(filename=str(log_path), level=logging.INFO,
                                format="%(asctime)s %(levelname)s %(message)s")
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            manifest = tg.Manifest(ROOT / "twin.manifest.json")
            backend = tg.PendingBackend()
            self.gw = tg.Gateway(manifest, backend, "127.0.0.1", self.ws_port, "", 10)
            self.started.set()
            self.loop.run_until_complete(self.gw.run())
        except Exception as exc:
            self.error = str(exc)
            logging.exception("gateway failed")
            self.started.set()
        finally:
            if self.loop:
                try:
                    self.loop.close()
                except Exception:
                    pass

    def stop(self):
        try:
            if self.httpd:
                self.httpd.shutdown()
        except Exception:
            pass
        if self.gw and self.loop:
            try:
                self.loop.call_soon_threadsafe(self.gw.stop_event.set)
            except Exception:
                pass


def run_headless(args):
    rt = Runtime()
    rt.start()
    print("PAGE_URL=" + rt.page_url, flush=True)
    print("WS_PORT=" + str(rt.ws_port), flush=True)
    print("按 Ctrl+C 停止。", flush=True)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        rt.stop()


def run_gui(args):
    import tkinter as tk
    from tkinter import messagebox
    from tkinter import ttk

    rt = Runtime()
    try:
        rt.start()
    except Exception as exc:
        try:
            messagebox.showerror("TIA Web Twin", f"启动失败：{exc}")
        except Exception:
            pass
        return 1

    root = tk.Tk()
    root.title("TIA Web Twin")
    root.configure(bg="#071019")
    root.geometry("460x230")
    root.resizable(False, False)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TButton", padding=(12, 8), font=("Segoe UI", 10))
    style.configure("Accent.TButton", padding=(12, 8), font=("Segoe UI", 10, "bold"))

    tk.Label(root, text="TIA Web Twin", bg="#071019", fg="#e7f1f8",
             font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(root, text="网页与本地 S7comm 网关已启动", bg="#071019", fg="#54e6a1",
             font=("Segoe UI", 9)).pack(anchor="w", padx=20)
    tk.Label(root, text="页面默认离线仿真；点右上角“连接 PLC”输入 PLCSIM Advanced 的 IP。",
             bg="#071019", fg="#8299ac", font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(10, 0))
    tk.Label(root, text="关闭此窗口即停止网页与网关。", bg="#071019", fg="#4d6578",
             font=("Segoe UI", 8)).pack(anchor="w", padx=20, pady=(6, 0))

    bar = tk.Frame(root, bg="#071019")
    bar.pack(fill="x", padx=20, pady=18)
    ttk.Button(bar, text="打开页面", style="Accent.TButton",
               command=lambda: webbrowser.open(rt.page_url)).pack(side="left")
    ttk.Button(bar, text="退出", command=lambda: on_close()).pack(side="left", padx=8)

    def on_close():
        rt.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    if not args.no_browser:
        root.after(500, lambda: webbrowser.open(rt.page_url))
    root.mainloop()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true", help="测试用：无窗口运行")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if args.headless:
        return run_headless(args)
    return run_gui(args)


if __name__ == "__main__":
    raise SystemExit(main())
