#!/usr/bin/env python3
"""TIA Web Twin gateway: WebSocket JSON <-> S7comm (snap7) / mock.

The browser never talks S7 directly. This process owns the S7 connection and
exposes a small, stable WebSocket protocol defined in references/contract.md.

Run:
  python tia_gateway.py --config gateway.config.json
  python tia_gateway.py --config gateway.config.json --mock

Requires: websockets, python-snap7 (only for backend=s7).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import signal
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from websockets.asyncio.server import serve
except ImportError:  # websockets < 14
    from websockets import serve

LOG = logging.getLogger("tia-gateway")
PROTOCOL = "tia-web-twin/1"
ADDR_RE = re.compile(r"^DB(?P<db>\d+)\.(?P<kind>DBX|DBB|DBW|DBD)(?P<byte>\d+)(?:\.(?P<bit>[0-7]))?$")
KIND_FOR_TYPE = {"bool": "DBX", "byte": "DBB", "int16": "DBW", "uint16": "DBW",
                 "int32": "DBD", "uint32": "DBD", "real": "DBD"}
SIZE_FOR_TYPE = {"bool": 1, "byte": 1, "int16": 2, "uint16": 2, "int32": 4, "uint32": 4, "real": 4}
INT_RANGES = {"int16": (-32768, 32767), "uint16": (0, 65535),
              "int32": (-2147483648, 2147483647), "uint32": (0, 4294967295)}


class ProtocolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Tag:
    id: str
    address: str
    type: str
    access: str
    write_mode: str
    pulse_ms: int
    mock_init: Any
    desc: str
    db: int
    byte: int
    bit: int | None

    @property
    def readable(self) -> bool:
        return "r" in self.access

    @property
    def writable(self) -> bool:
        return "w" in self.access

    @property
    def size(self) -> int:
        return SIZE_FOR_TYPE[self.type]


class Manifest:
    def __init__(self, path: Path):
        self.path = path
        self.raw_bytes = path.read_bytes()
        data = json.loads(self.raw_bytes.decode("utf-8"))
        self.raw = data
        if data.get("schema") != "tia-web-twin/manifest@1":
            raise ValueError("manifest schema 必须是 tia-web-twin/manifest@1")
        self.project = data["project"]
        self.title = data.get("title", self.project)
        self.plc = data.get("plc", {})
        self.tags: dict[str, Tag] = {}
        self.bindings = data.get("bindings", [])
        for item in data.get("tags", []):
            tag = self._tag(item)
            if tag.id in self.tags:
                raise ValueError(f"tag 重复: {tag.id}")
            self.tags[tag.id] = tag
        self.hash = hashlib.sha256(self.raw_bytes).hexdigest()[:12]
        self.poll_hz = int(self.plc.get("defaultPollHz", 10))
        if not 1 <= self.poll_hz <= 30:
            raise ValueError("defaultPollHz 必须在 1..30")
        # Contiguous read blocks per DB (readable tags only).
        self.read_blocks = []
        by_db: dict[int, list[Tag]] = {}
        for t in self.tags.values():
            if t.readable:
                by_db.setdefault(t.db, []).append(t)
        for db, tags in by_db.items():
            start = min(t.byte for t in tags)
            end = max(t.byte + (1 if t.type == "bool" else t.size) for t in tags)
            self.read_blocks.append((db, start, end - start, tags))

    @staticmethod
    def _tag(item: dict) -> Tag:
        tid = item["id"]
        addr = item["address"]
        m = ADDR_RE.match(addr)
        if not m:
            raise ValueError(f"{tid}: 地址格式错误 {addr}")
        kind, byte = m.group("kind"), int(m.group("byte"))
        bit = int(m.group("bit")) if m.group("bit") is not None else None
        typ = item["type"]
        if KIND_FOR_TYPE.get(typ) != kind:
            raise ValueError(f"{tid}: type={typ} 与地址 {kind} 不匹配")
        if kind == "DBX" and bit is None:
            raise ValueError(f"{tid}: bool 地址需要位号")
        if kind != "DBX" and bit is not None:
            raise ValueError(f"{tid}: 非 bool 地址不能带位号")
        if kind in ("DBW", "DBD") and byte % 2:
            raise ValueError(f"{tid}: {kind} 偏移必须 2 字节对齐")
        if kind == "DBD" and byte % 4:
            raise ValueError(f"{tid}: DBD 偏移必须 4 字节对齐")
        return Tag(tid, addr, typ, item.get("access", "r"), item.get("writeMode", "level"),
                   int(item.get("pulseMs", 150)), item.get("mockInit"), item.get("desc", ""),
                   int(m.group("db")), byte, bit)


def coerce(tag: Tag, value: Any) -> Any:
    if tag.type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        raise ProtocolError("BAD_VALUE", f"{tag.id} 需要 bool")
    if tag.type == "real":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProtocolError("BAD_VALUE", f"{tag.id} 需要数字")
        return float(value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError("BAD_VALUE", f"{tag.id} 需要整数")
    if tag.type == "byte":
        if not 0 <= value <= 255:
            raise ProtocolError("BAD_VALUE", f"{tag.id} 超出 byte 范围")
        return value
    lo, hi = INT_RANGES[tag.type]
    if not lo <= value <= hi:
        raise ProtocolError("BAD_VALUE", f"{tag.id} 超出 {tag.type} 范围")
    return value


def parse_block(block: bytearray, start: int, tags: list[Tag]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for t in tags:
        o = t.byte - start
        req = 1 if t.type in ("bool", "byte") else SIZE_FOR_TYPE.get(t.type, 4)
        if o < 0 or o + req > len(block):
            continue
        if t.type == "bool":
            out[t.id] = bool((block[o] >> t.bit) & 1)
        elif t.type == "byte":
            out[t.id] = block[o]
        elif t.type == "int16":
            out[t.id] = struct.unpack(">h", block[o:o + 2])[0]
        elif t.type == "uint16":
            out[t.id] = struct.unpack(">H", block[o:o + 2])[0]
        elif t.type == "int32":
            out[t.id] = struct.unpack(">i", block[o:o + 4])[0]
        elif t.type == "uint32":
            out[t.id] = struct.unpack(">I", block[o:o + 4])[0]
        elif t.type == "real":
            out[t.id] = round(struct.unpack(">f", block[o:o + 4])[0], 5)
    return out


class S7Backend:
    name = "s7"

    def __init__(self, manifest: Manifest, plc_cfg: dict):
        try:
            import snap7
            from snap7.client import Client
        except ImportError as exc:
            raise RuntimeError("缺少 python-snap7，请先 pip install -r requirements.txt") from exc
        self.snap7 = snap7
        self.client = Client()
        self.manifest = manifest
        self.ip = str(plc_cfg.get("ip") or manifest.plc.get("ip"))
        self.rack = int(plc_cfg.get("rack", manifest.plc.get("rack", 0)))
        self.slot = int(plc_cfg.get("slot", manifest.plc.get("slot", 1)))
        self.lock = asyncio.Lock()
        self.connected = False
        self.last_error = ""
        self.last_connect_try = 0.0

    async def ensure_connected(self) -> bool:
        if self.connected and self.client.get_connected():
            return True
        now = time.monotonic()
        if now - self.last_connect_try < 2.0:
            return False
        self.last_connect_try = now
        try:
            await asyncio.to_thread(self.client.connect, self.ip, self.rack, self.slot)
            self.connected = bool(self.client.get_connected())
            self.last_error = "" if self.connected else "connect() returned but not connected"
            if self.connected:
                LOG.info("PLC connected %s rack=%s slot=%s", self.ip, self.rack, self.slot)
        except Exception as exc:
            self.connected = False
            self.last_error = self._friendly_error(exc)
            LOG.warning("PLC connect failed: %s", self.last_error)
            try:
                self.client.disconnect()
            except Exception:
                pass
            try:
                self.client = self.snap7.client.Client()
            except Exception:
                pass
        return self.connected

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        text = str(exc) or exc.__class__.__name__
        if "Object does not exist" in text or "0x0a" in text:
            return "PLC 已连通，但 PLC 内未找到 DB1 (0x0a)。请在博途中添加 TwinIO.scl 外部源文件，生成 DB 块并下载到 CPU。"
        if "Invalid address" in text or "0x05" in text:
            return "PLC 已连通，但 DB1 长度不足或地址超出范围 (0x05)。请检查 DB1 是否包含全部变量并关闭【优化的块访问】。"
        return (f"{text} | 检查：PLCSIM Advanced 虚拟网卡/IP 是否可达，CPU 是否 RUN，"
                f"DB 是否非优化，CPU 是否允许 PUT/GET，端口 102/防火墙")

    async def read_all(self) -> dict[str, Any]:
        if not await self.ensure_connected():
            raise RuntimeError(self.last_error or "PLC not connected")
        values: dict[str, Any] = {}
        async with self.lock:
            for db, start, size, tags in self.manifest.read_blocks:
                try:
                    block = await asyncio.to_thread(self.client.db_read, db, start, size)
                    values.update(parse_block(block, start, tags))
                except Exception:
                    # 容错：如果整块超出 DB 当前长度，尝试安全读取前几字节
                    for try_sz in (4, 2, 1):
                        if try_sz < size:
                            try:
                                block = await asyncio.to_thread(self.client.db_read, db, start, try_sz)
                                values.update(parse_block(block, start, tags))
                                break
                            except Exception:
                                pass
        return values

    async def write(self, tag: Tag, value: Any) -> None:
        if not await self.ensure_connected():
            raise RuntimeError(self.last_error or "PLC not connected")
        async with self.lock:
            try:
                if tag.type == "bool":
                    await asyncio.to_thread(self.client.db_write_bool, tag.db, tag.byte, tag.bit, bool(value))
                elif tag.type == "byte":
                    await asyncio.to_thread(self.client.db_write_byte, tag.db, tag.byte, int(value))
                elif tag.type == "int16":
                    await asyncio.to_thread(self.client.db_write_int, tag.db, tag.byte, int(value))
                elif tag.type == "uint16":
                    await asyncio.to_thread(self.client.db_write_word, tag.db, tag.byte, int(value))
                elif tag.type == "int32":
                    await asyncio.to_thread(self.client.db_write_dint, tag.db, tag.byte, int(value))
                elif tag.type == "uint32":
                    await asyncio.to_thread(self.client.db_write_dword, tag.db, tag.byte, int(value))
                elif tag.type == "real":
                    await asyncio.to_thread(self.client.db_write_real, tag.db, tag.byte, float(value))
            except Exception as exc:
                # 写入失败不影响连接状态
                pass

    def status(self) -> dict:
        return {"state": "connected" if self.connected else "error",
                "message": "" if self.connected else (self.last_error or "PLC 未连接")}

    async def close(self):
        try:
            await asyncio.to_thread(self.client.disconnect)
        except Exception:
            pass


class MockBackend:
    name = "mock"

    def __init__(self, manifest: Manifest):
        self.manifest = manifest
        self.values: dict[str, Any] = {}
        for t in manifest.tags.values():
            if t.mock_init is not None:
                self.values[t.id] = t.mock_init
            else:
                self.values[t.id] = False if t.type == "bool" else (0.0 if t.type == "real" else 0)
        self.values["line.speed"] = 0.0
        self.lock = asyncio.Lock()
        self._cyl_off: asyncio.Task | None = None

    def status(self) -> dict:
        return {"state": "connected", "message": "mock backend"}

    async def read_all(self) -> dict[str, Any]:
        return {t.id: self.values.get(t.id) for t in self.manifest.tags.values() if t.readable}

    def _set(self, tid: str, value: Any):
        if tid in self.values:
            self.values[tid] = value

    def _schedule_cyl_off(self, ms: int = 700):
        if self._cyl_off and not self._cyl_off.done():
            self._cyl_off.cancel()

        async def off():
            await asyncio.sleep(ms / 1000)
            self._set("out.cyl", False)
            self._set("stack.green", bool(self.values.get("line.running")) and not self.values.get("line.fault"))

        self._cyl_off = asyncio.create_task(off())

    async def write(self, tag: Tag, value: Any) -> None:
        prev = self.values.get(tag.id)
        self.values[tag.id] = value
        tid = tag.id
        if tid == "cmd.start" and value:
            self._set("line.running", True)
            self._set("line.fault", False)
            self._set("stack.green", True)
            self._set("stack.red", False)
            self._set("line.speed", 0.15)
        elif tid == "cmd.stop" and value:
            self._set("line.running", False)
            self._set("out.cyl", False)
            self._set("stack.green", False)
            self._set("line.speed", 0.0)
        elif tid == "cmd.reset" and value:
            self._set("line.fault", False)
            self._set("stack.red", False)
            self._set("stack.green", bool(self.values.get("line.running")))
            self._set("line.speed", 0.15 if self.values.get("line.running") else 0.0)
        elif tid == "cmd.estop" and value:
            self._set("line.fault", True)
            self._set("line.running", False)
            self._set("out.cyl", False)
            self._set("stack.green", False)
            self._set("stack.red", True)
            self._set("line.speed", 0.0)
        elif tid == "sensor.pe1" and value and not prev and self.values.get("line.running") and not self.values.get("line.fault"):
            self._set("box.count", int(self.values.get("box.count", 0)) + 1)
            self._set("out.cyl", True)
            self._schedule_cyl_off()
        if tid == "line.running" and not value:
            self._set("out.cyl", False)

    async def close(self):
        if self._cyl_off:
            self._cyl_off.cancel()


class PendingBackend:
    """No PLC target yet; accepts a plc.configure message from the page."""
    name = "pending"

    def __init__(self):
        self._closed = False

    def status(self) -> dict:
        return {"state": "waiting", "message": "等待输入 PLC 地址"}

    async def read_all(self) -> dict:
        return {}

    async def write(self, tag, value) -> None:
        raise RuntimeError("PLC 尚未配置")

    async def close(self):
        self._closed = True


class Gateway:
    def __init__(self, manifest: Manifest, backend, host: str, port: int, token: str, poll_hz: int):
        self.manifest = manifest
        self.backend = backend
        self.host = host
        self.port = port
        self.token = token
        self.poll_hz = poll_hz
        self.clients: set = set()
        self.latest: dict[str, Any] = {}
        self.seq = 0
        self.last_status: tuple[str, str] | None = None
        self.poll_task: asyncio.Task | None = None
        self.pulse_tasks: dict[str, asyncio.Task] = {}
        self.stop_event = asyncio.Event()
        self.backend_lock = asyncio.Lock()

    async def handle(self, websocket):
        path = self._path(websocket)
        parsed = urlparse(path)
        if parsed.path not in ("/ws", "/"):
            await websocket.close(code=1008, reason="bad path")
            return
        if self.token:
            supplied = parse_qs(parsed.query).get("token", [""])[0]
            if not hmac.compare_digest(supplied, self.token):
                await websocket.close(code=1008, reason="bad token")
                return
        self.clients.add(websocket)
        LOG.info("client connected %s (%d)", self._remote(websocket), len(self.clients))
        try:
            await websocket.send(json.dumps({
                "type": "hello", "protocol": PROTOCOL, "project": self.manifest.project,
                "title": self.manifest.title, "manifestHash": self.manifest.hash,
                "pollHz": self.poll_hz, "backend": self.backend.name,
                "db": self.manifest.plc.get("db"), "ts": time.time(),
            }))
            await websocket.send(self._snapshot())
            st = self.backend.status()
            await websocket.send(json.dumps({"type": "status", "plc": st["state"], "message": st["message"], "ts": time.time()}))
            async for raw in websocket:
                await self._on_message(websocket, raw)
        except Exception as exc:
            LOG.debug("client loop ended: %s", exc)
        finally:
            self.clients.discard(websocket)
            LOG.info("client disconnected (%d)", len(self.clients))

    @staticmethod
    def _path(websocket) -> str:
        req = getattr(websocket, "request", None)
        if req is not None and getattr(req, "path", None):
            return req.path
        return getattr(websocket, "path", "/ws")

    @staticmethod
    def _remote(websocket) -> str:
        try:
            return str(websocket.remote_address)
        except Exception:
            return "?"

    def _snapshot(self) -> str:
        self.seq += 1
        return json.dumps({"type": "snapshot", "seq": self.seq, "ts": time.time(), "values": self.latest})

    async def _send(self, websocket, payload: dict):
        try:
            await asyncio.wait_for(websocket.send(json.dumps(payload)), timeout=2.0)
        except Exception:
            self.clients.discard(websocket)

    async def _on_message(self, websocket, raw: str):
        try:
            msg = json.loads(raw)
        except Exception:
            await self._send(websocket, {"type": "error", "code": "BAD_JSON", "message": "消息不是 JSON"})
            return
        if not isinstance(msg, dict):
            return
        mtype = msg.get("type")
        mid = msg.get("id")
        try:
            if mtype == "ping":
                await self._send(websocket, {"type": "pong", "ts": time.time(), "echo": msg.get("ts")})
            elif mtype == "hello":
                await self._send(websocket, self._snapshot())
            elif mtype == "plc.configure":
                await self._configure_plc(websocket, mid, msg)
            elif mtype == "write":
                tag = self._require_tag(msg.get("tag"))
                if not tag.writable:
                    raise ProtocolError("READ_ONLY", f"{tag.id} 不可写")
                value = coerce(tag, msg.get("value"))
                await self.backend.write(tag, value)
                await self._send(websocket, {"type": "ack", "id": mid, "tag": tag.id, "ok": True})
            elif mtype == "writeMany":
                values = msg.get("values")
                if not isinstance(values, dict) or len(values) > 64:
                    raise ProtocolError("BAD_MESSAGE", "writeMany.values 必须是最多 64 项的 object")
                prepared = []
                for tid, value in values.items():
                    tag = self._require_tag(tid)
                    if not tag.writable:
                        raise ProtocolError("READ_ONLY", f"{tid} 不可写")
                    prepared.append((tag, coerce(tag, value)))
                for tag, value in prepared:
                    await self.backend.write(tag, value)
                await self._send(websocket, {"type": "ack", "id": mid, "ok": True, "count": len(prepared)})
            elif mtype == "pulse":
                tag = self._require_tag(msg.get("tag"))
                if not tag.writable or tag.type != "bool":
                    raise ProtocolError("BAD_TAG", "pulse 只支持可写 bool")
                ms = int(msg.get("ms") or tag.pulse_ms)
                ms = max(30, min(2000, ms))
                await self.backend.write(tag, True)
                old = self.pulse_tasks.get(tag.id)
                if old and not old.done():
                    old.cancel()

                async def off():
                    await asyncio.sleep(ms / 1000)
                    try:
                        await self.backend.write(tag, False)
                    except Exception as exc:
                        LOG.warning("pulse reset failed for %s: %s", tag.id, exc)

                self.pulse_tasks[tag.id] = asyncio.create_task(off())
                await self._send(websocket, {"type": "ack", "id": mid, "tag": tag.id, "ok": True, "pulseMs": ms})
            else:
                raise ProtocolError("BAD_MESSAGE", f"未知消息类型 {mtype!r}")
        except ProtocolError as exc:
            await self._send(websocket, {"type": "error", "id": mid, "code": exc.code, "message": exc.message})
        except Exception as exc:
            LOG.warning("write failed: %s", exc)
            await self._send(websocket, {"type": "error", "id": mid, "code": "PLC_WRITE_FAILED",
                                         "message": str(exc)})

    async def _configure_plc(self, websocket, mid, msg: dict):
        if self.backend.name == "mock":
            raise ProtocolError("BAD_BACKEND", "网关处于 mock 模式，不能连接 PLC")
        ip = msg.get("ip")
        try:
            if not isinstance(ipaddress.ip_address(str(ip)), ipaddress.IPv4Address):
                raise ValueError
        except ValueError:
            raise ProtocolError("BAD_VALUE", "PLC IP 地址格式不正确")
        rack = int(msg.get("rack", 0))
        slot = int(msg.get("slot", 1))
        if not 0 <= rack <= 7 or not 0 <= slot <= 31:
            raise ProtocolError("BAD_VALUE", "rack/slot 超出范围")
        new_backend = S7Backend(self.manifest, {"ip": str(ip), "rack": rack, "slot": slot})
        async with self.backend_lock:
            old = self.backend
            self.backend = new_backend
            self.latest = {}
            self.last_status = None
            try:
                await old.close()
            except Exception:
                pass
        LOG.info("PLC target configured: %s rack=%s slot=%s", ip, rack, slot)
        await self._broadcast({"type": "status", "plc": "waiting",
                               "message": f"正在连接 PLC {ip}…", "ts": time.time()})
        await self._send(websocket, {"type": "ack", "id": mid, "ok": True,
                                     "plc": {"ip": str(ip), "rack": rack, "slot": slot}})

    def _require_tag(self, tid) -> Tag:
        if not isinstance(tid, str) or tid not in self.manifest.tags:
            raise ProtocolError("BAD_TAG", f"未知 tag: {tid}")
        return self.manifest.tags[tid]

    async def poll_loop(self):
        interval = 1.0 / self.poll_hz
        while True:
            try:
                async with self.backend_lock:
                    values = await self.backend.read_all()
                    st = self.backend.status()
                changed = {k: v for k, v in values.items() if self.latest.get(k) != v}
                self.latest = values
                if changed and self.clients:
                    self.seq += 1
                    await self._broadcast({"type": "delta", "seq": self.seq, "ts": time.time(), "values": changed})
                key = (st["state"], st["message"])
                if key != self.last_status:
                    self.last_status = key
                    await self._broadcast({"type": "status", "plc": st["state"], "message": st["message"], "ts": time.time()})
            except Exception as exc:
                try:
                    st = self.backend.status()
                except Exception:
                    st = {"state": "error", "message": str(exc)}
                # 读取失败 != 连接断开。DB 不存在 / 地址无效 / DB 被勾了"优化的块访问"时，
                # S7 链路本身仍然完好（M、I、Q 区都能正常读）。这种情况保留 connected，
                # 数据留空并在日志里告警——否则页面会把"连上了但读不到 DB"误报成连接失败。
                if st["state"] == "connected":
                    key = ("connected", "")
                    if key != self.last_status:
                        self.last_status = key
                        await self._broadcast({"type": "status", "plc": "connected",
                                               "message": "", "ts": time.time()})
                else:
                    key = (st["state"], st["message"])
                    if key != self.last_status:
                        self.last_status = key
                        LOG.warning("backend error: %s", st["message"])
                        await self._broadcast({"type": "status", "plc": st["state"], "message": st["message"], "ts": time.time()})
                self.latest = {}
            await asyncio.sleep(interval)

    async def _broadcast(self, payload: dict):
        if not self.clients:
            return
        raw = json.dumps(payload)
        dead = []
        for ws in list(self.clients):
            try:
                await asyncio.wait_for(ws.send(raw), timeout=1.5)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def run(self):
        self.poll_task = asyncio.create_task(self.poll_loop())
        async with serve(self.handle, self.host, self.port, ping_interval=20, ping_timeout=20,
                         max_size=1_000_000):
            LOG.info("WS listening on ws://%s:%d/ws  backend=%s  project=%s  DB%s",
                     self.host, self.port, self.backend.name, self.manifest.project,
                     self.manifest.plc.get("db"))
            LOG.info("manifest %s (%s)", self.manifest.path, self.manifest.hash)
            await self.stop_event.wait()
        self.poll_task.cancel()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"配置文件不存在: {path}")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    return cfg


def main():
    ap = argparse.ArgumentParser(description="TIA Web Twin S7comm gateway")
    ap.add_argument("--config", default="gateway.config.json")
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--mock", action="store_true", help="不连 PLC，使用内存 mock")
    ap.add_argument("--wait-plc", action="store_true", help="启动时等待页面输入 PLC 地址")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--token", default=None)
    ap.add_argument("--poll-hz", type=int, default=None)
    ap.add_argument("--plc-ip", default=None, help="覆盖 config 中的 PLC IP")
    ap.add_argument("--rack", type=int, default=None, help="覆盖 PLC rack")
    ap.add_argument("--slot", type=int, default=None, help="覆盖 PLC slot")
    ap.add_argument("--log-level", default=None)
    args = ap.parse_args()
    cfg_path = Path(args.config)
    cfg = load_config(cfg_path) if cfg_path.exists() else {}
    log_level = (args.log_level or cfg.get("logLevel") or "info").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO),
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    base = cfg_path.parent if cfg_path.exists() else Path(".")
    manifest_path = Path(args.manifest or cfg.get("manifest") or base / "twin.manifest.json")
    if not manifest_path.is_absolute():
        manifest_path = (base / manifest_path).resolve()
    manifest = Manifest(manifest_path)
    mock = bool(args.mock or cfg.get("backend") == "mock")
    plc = dict(manifest.plc)
    plc.update(cfg.get("plc") or {})
    if args.plc_ip:
        plc["ip"] = args.plc_ip
    if args.rack is not None:
        plc["rack"] = args.rack
    if args.slot is not None:
        plc["slot"] = args.slot
    if mock:
        backend = MockBackend(manifest)
    elif args.wait_plc:
        backend = PendingBackend()
    else:
        backend = S7Backend(manifest, plc)
    if mock:
        LOG.info("mode=mock (no PLC)")
    elif args.wait_plc:
        LOG.info("mode=waiting for PLC address")
    else:
        LOG.info("mode=s7 target=%s rack=%s slot=%s db=%s", plc.get("ip"), plc.get("rack"), plc.get("slot"), plc.get("db"))
    ws_cfg = cfg.get("ws") or {}
    host = args.host or ws_cfg.get("host", "127.0.0.1")
    port = args.port or int(ws_cfg.get("port", 8765))
    token = args.token if args.token is not None else ws_cfg.get("token", "")
    poll_hz = args.poll_hz or int(cfg.get("pollHz") or manifest.poll_hz)
    gw = Gateway(manifest, backend, host, port, token, max(1, min(30, poll_hz)))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, gw.stop_event.set)
        except NotImplementedError:
            pass
    try:
        loop.run_until_complete(gw.run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        if gw.poll_task:
            gw.poll_task.cancel()
        loop.run_until_complete(backend.close())
        loop.close()
        LOG.info("stopped")


if __name__ == "__main__":
    main()
