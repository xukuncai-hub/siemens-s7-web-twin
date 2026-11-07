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

# 西门子 S7 存储区域代码 (Snap7 Area Constants)
S7_AREAS = {
    "DB": 0x84,
    "I": 0x81,   # 过程映像输入 (PE)
    "Q": 0x82,   # 过程映像输出 (PA)
    "M": 0x83,   # 内部位存储器 (MK)
}

# 支持 DBn.DBX/DBB/DBW/DBD 以及原生的 I/Q/M/IW/QW/MW/MD/ID/QD
ADDR_RE = re.compile(
    r"^(?:"
    r"DB(?P<db>\d+)\.(?P<dbkind>DBX|DBB|DBW|DBD)(?P<dbbyte>\d+)(?:\.(?P<dbbit>[0-7]))?|"
    r"(?P<area>[IQM])(?P<kind>[XBWDL]?)(?P<byte>\d+)(?:\.(?P<bit>[0-7]))?"
    r")$",
    re.IGNORECASE
)
MODBUS_ADDR_RE = re.compile(
    r"^(?:(?P<slave>\d+)#)?(?:(?P<prefix>0x|1x|3x|4x)(?P<reg1>\d+)|(?P<area>coil|di|ir|hr):(?P<reg2>\d+)(?:\.(?P<bit>[0-7]))?|(?P<num>\d{5}))$",
    re.IGNORECASE
)
RAW_ADDR_RE = re.compile(r"^(?:offset|byte):(?P<byte>\d+)(?:\.(?P<bit>[0-7]))?$", re.IGNORECASE)
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
    area: str | None = None
    area_code: int = 0x84
    reg: int | None = None
    slave_id: int | None = None

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
        self.protocol = str(data.get("protocol") or self.plc.get("protocol", "s7")).lower()
        self.tags: dict[str, Tag] = {}
        self.bindings = data.get("bindings", [])
        for item in data.get("tags", []):
            tag = self._parse_tag(item, self.protocol)
            if tag.id in self.tags:
                raise ValueError(f"tag 重复: {tag.id}")
            self.tags[tag.id] = tag
        self.hash = hashlib.sha256(self.raw_bytes).hexdigest()[:12]
        self.poll_hz = int(self.plc.get("defaultPollHz", 10))
        if not 1 <= self.poll_hz <= 30:
            raise ValueError("defaultPollHz 必须在 1..30")

        # 按 (area_code, db) 分组的最优连续块读取 (支持多 DB、I区、Q区、M区)
        self.read_blocks = []
        if self.protocol in ("s7", "s7comm", "siemens"):
            by_area_db: dict[tuple[int, int], list[Tag]] = {}
            for t in self.tags.values():
                if t.readable:
                    by_area_db.setdefault((t.area_code, t.db), []).append(t)
            for (area_code, db), tags in by_area_db.items():
                start = min(t.byte for t in tags)
                end = max(t.byte + (1 if t.type == "bool" else t.size) for t in tags)
                self.read_blocks.append((area_code, db, start, end - start, tags))

    @staticmethod
    def _parse_tag(item: dict, protocol: str = "s7") -> Tag:
        tid = item["id"]
        addr = str(item.get("address", ""))
        typ = item["type"]
        access = item.get("access", "r")
        mode = item.get("writeMode", "level")
        pulse_ms = int(item.get("pulseMs", 150))
        mock_init = item.get("mockInit")
        desc = item.get("desc", "")
        proto = protocol.lower()

        if proto in ("s7", "s7comm", "siemens"):
            m = ADDR_RE.match(addr)
            if not m:
                raise ValueError(f"{tid}: S7 地址格式错误 {addr} (支持 DB1.DBX0.0 / I0.0 / Q0.0 / IW64 / QW64 / M0.0 / MW10 等)")
            if m.group("db"):
                area_name = "DB"
                area_code = 0x84
                db = int(m.group("db"))
                kind = m.group("dbkind").upper()
                byte = int(m.group("dbbyte"))
                bit = int(m.group("dbbit")) if m.group("dbbit") is not None else None
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
            else:
                area_name = m.group("area").upper()
                area_code = S7_AREAS[area_name]
                db = 0
                byte = int(m.group("byte"))
                bit = int(m.group("bit")) if m.group("bit") is not None else None
                raw_kind = (m.group("kind") or "").upper()
                if typ == "bool":
                    if bit is None:
                        raise ValueError(f"{tid}: {area_name} 布尔量地址必须带位号，如 {area_name}0.0")
                elif typ == "byte":
                    if bit is not None or (raw_kind and raw_kind != "B"):
                        raise ValueError(f"{tid}: byte 类型地址应为 {area_name}B{byte}")
                elif typ in ("int16", "uint16"):
                    if bit is not None or (raw_kind and raw_kind != "W"):
                        raise ValueError(f"{tid}: {typ} 类型地址应为 {area_name}W{byte}")
                    if byte % 2:
                        raise ValueError(f"{tid}: {area_name}W{byte} 必须 2 字节对齐")
                elif typ in ("int32", "uint32", "real"):
                    if bit is not None or (raw_kind and raw_kind not in ("D", "L")):
                        raise ValueError(f"{tid}: {typ} 类型地址应为 {area_name}D{byte}")
                    if byte % 2:
                        raise ValueError(f"{tid}: {area_name}D{byte} 必须偶数字节对齐")

            return Tag(tid, addr, typ, access, mode, pulse_ms, mock_init, desc,
                       db, byte, bit, area=area_name, area_code=area_code)
        elif proto in ("modbus-tcp", "modbus-rtu", "modbus", "modbus_tcp", "modbus_rtu", "rs485"):
            m = MODBUS_ADDR_RE.match(addr)
            if not m:
                raise ValueError(f"{tid}: Modbus 地址格式错误 {addr}")
            slave_id = int(m.group("slave")) if m.group("slave") else None
            area = "hr"
            reg = 1
            bit = None
            if m.group("prefix"):
                pfx = m.group("prefix").lower()
                reg = int(m.group("reg1"))
                area = {"0x": "coil", "1x": "di", "3x": "ir", "4x": "hr"}[pfx]
            elif m.group("area"):
                area = m.group("area").lower()
                reg = int(m.group("reg2"))
                bit = int(m.group("bit")) if m.group("bit") is not None else None
            elif m.group("num"):
                num = int(m.group("num"))
                if num < 10000:
                    area, reg = "coil", num
                elif num < 20000:
                    area, reg = "di", num - 10000
                elif num < 40000:
                    area, reg = "ir", num - 30000
                else:
                    area, reg = "hr", num - 40000
            return Tag(tid, addr, typ, access, mode, pulse_ms, mock_init, desc,
                       0, reg * 2, bit, area=area, reg=reg, slave_id=slave_id)
        elif proto in ("tcp-raw", "raw-tcp", "socket"):
            m = RAW_ADDR_RE.match(addr)
            if not m:
                raise ValueError(f"{tid}: Raw TCP 地址格式错误 {addr}")
            byte = int(m.group("byte"))
            bit = int(m.group("bit")) if m.group("bit") is not None else None
            return Tag(tid, addr, typ, access, mode, pulse_ms, mock_init, desc,
                       0, byte, bit)
        else:
            return Tag(tid, addr, typ, access, mode, pulse_ms, mock_init, desc,
                       0, 0, None)


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


class BaseProtocolBackend:
    name: str = "base"

    def status(self) -> dict:
        return {"state": "unknown", "message": "unimplemented"}

    async def ensure_connected(self) -> bool:
        return True

    async def read_all(self) -> dict[str, Any]:
        return {}

    async def write(self, tag: Tag, value: Any) -> None:
        pass

    async def close(self) -> None:
        pass


class S7Backend(BaseProtocolBackend):
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
            for area_code, db, start, size, tags in self.manifest.read_blocks:
                try:
                    block = await asyncio.to_thread(self.client.read_area, area_code, db, start, size)
                    values.update(parse_block(block, start, tags))
                except Exception:
                    # 容错：如果整块超出范围，尝试逐个安全读取
                    for try_sz in (4, 2, 1):
                        if try_sz < size:
                            try:
                                block = await asyncio.to_thread(self.client.read_area, area_code, db, start, try_sz)
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
                area = tag.area_code
                db = tag.db
                byte = tag.byte
                if tag.type == "bool":
                    cur = await asyncio.to_thread(self.client.read_area, area, db, byte, 1)
                    b = cur[0]
                    bit = tag.bit if tag.bit is not None else 0
                    if value:
                        b |= (1 << bit)
                    else:
                        b &= ~(1 << bit)
                    await asyncio.to_thread(self.client.write_area, area, db, byte, bytearray([b]))
                elif tag.type == "byte":
                    await asyncio.to_thread(self.client.write_area, area, db, byte, bytearray([int(value) & 0xFF]))
                elif tag.type in ("int16", "uint16"):
                    raw = struct.pack(">h" if tag.type == "int16" else ">H", int(value))
                    await asyncio.to_thread(self.client.write_area, area, db, byte, bytearray(raw))
                elif tag.type in ("int32", "uint32"):
                    raw = struct.pack(">i" if tag.type == "int32" else ">I", int(value))
                    await asyncio.to_thread(self.client.write_area, area, db, byte, bytearray(raw))
                elif tag.type == "real":
                    raw = struct.pack(">f", float(value))
                    await asyncio.to_thread(self.client.write_area, area, db, byte, bytearray(raw))
            except Exception as exc:
                LOG.warning("PLC write failed for tag %s (%s): %s", tag.id, tag.address, exc)

    def status(self) -> dict:
        return {"state": "connected" if self.connected else "error",
                "message": "" if self.connected else (self.last_error or "PLC 未连接")}

    async def close(self):
        try:
            await asyncio.to_thread(self.client.disconnect)
        except Exception:
            pass


class ModbusTcpBackend(BaseProtocolBackend):
    name = "modbus-tcp"

    def __init__(self, manifest: Manifest, cfg: dict):
        self.manifest = manifest
        self.ip = str(cfg.get("ip") or manifest.plc.get("ip", "127.0.0.1"))
        self.port = int(cfg.get("port") or manifest.plc.get("port", 502))
        self.slave_id = int(cfg.get("slaveId") or manifest.plc.get("slaveId", 1))
        self.reader = None
        self.writer = None
        self.connected = False
        self.last_error = ""
        self.last_connect_try = 0.0
        self.trans_id = 0
        self.lock = asyncio.Lock()

    def _next_tid(self) -> int:
        self.trans_id = (self.trans_id + 1) & 0xFFFF
        return self.trans_id

    async def ensure_connected(self) -> bool:
        if self.connected and self.writer and not self.writer.is_closing():
            return True
        now = time.monotonic()
        if now - self.last_connect_try < 2.0:
            return False
        self.last_connect_try = now
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), timeout=3.0
            )
            self.connected = True
            self.last_error = ""
            LOG.info("Modbus TCP connected to %s:%d (slaveId=%d)", self.ip, self.port, self.slave_id)
        except Exception as exc:
            self.connected = False
            self.last_error = f"Modbus TCP 连接失败: {exc}"
            LOG.warning("Modbus TCP 连接失败 (%s:%d): %s", self.ip, self.port, exc)
            if self.writer:
                try:
                    self.writer.close()
                except Exception:
                    pass
        return self.connected

    async def _send_modbus(self, fc: int, data: bytes, slave_id: int | None = None) -> bytes:
        unit = self.slave_id if slave_id is None else slave_id
        tid = self._next_tid()
        pdu = bytes([fc]) + data
        adu = struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu
        self.writer.write(adu)
        await self.writer.drain()

        hdr = await asyncio.wait_for(self.reader.readexactly(7), timeout=2.0)
        resp_tid, proto_id, resp_len, resp_unit = struct.unpack(">HHHB", hdr)
        resp_pdu = await asyncio.wait_for(self.reader.readexactly(resp_len - 1), timeout=2.0)
        resp_fc = resp_pdu[0]
        if resp_fc == (fc | 0x80):
            err_code = resp_pdu[1] if len(resp_pdu) > 1 else 0
            raise RuntimeError(f"Modbus 异常响应: FC={resp_fc:#x}, code={err_code}")
        return resp_pdu[1:]

    async def read_all(self) -> dict[str, Any]:
        if not await self.ensure_connected():
            raise RuntimeError(self.last_error or "Modbus TCP 未连接")
        out = {}
        async with self.lock:
            for t in self.manifest.tags.values():
                if not t.readable:
                    continue
                try:
                    val = await self._read_tag(t)
                    if val is not None:
                        out[t.id] = val
                except Exception as exc:
                    LOG.debug("读取 tag %s 失败: %s", t.id, exc)
        return out

    async def _read_tag(self, tag: Tag) -> Any:
        area = tag.area or "hr"
        reg = max(0, (tag.reg or 1) - 1)
        slave = tag.slave_id or self.slave_id

        if area == "coil":
            data = struct.pack(">HH", reg, 1)
            resp = await self._send_modbus(1, data, slave)
            return bool(resp[1] & 0x01)
        elif area == "di":
            data = struct.pack(">HH", reg, 1)
            resp = await self._send_modbus(2, data, slave)
            return bool(resp[1] & 0x01)
        elif area in ("ir", "hr"):
            fc = 4 if area == "ir" else 3
            count = 2 if tag.size == 4 else 1
            data = struct.pack(">HH", reg, count)
            resp = await self._send_modbus(fc, data, slave)
            reg_bytes = resp[1:]
            if tag.type == "bool":
                bit = tag.bit if tag.bit is not None else 0
                word = struct.unpack(">H", reg_bytes[:2])[0]
                return bool((word >> bit) & 1)
            elif tag.type == "int16":
                return struct.unpack(">h", reg_bytes[:2])[0]
            elif tag.type in ("uint16", "byte"):
                return struct.unpack(">H", reg_bytes[:2])[0]
            elif tag.type == "int32":
                return struct.unpack(">i", reg_bytes[:4])[0]
            elif tag.type == "uint32":
                return struct.unpack(">I", reg_bytes[:4])[0]
            elif tag.type == "real":
                return round(struct.unpack(">f", reg_bytes[:4])[0], 4)
        return None

    async def write(self, tag: Tag, value: Any) -> None:
        if not await self.ensure_connected():
            raise RuntimeError(self.last_error or "Modbus TCP 未连接")
        area = tag.area or "hr"
        reg = max(0, (tag.reg or 1) - 1)
        slave = tag.slave_id or self.slave_id

        async with self.lock:
            try:
                if area == "coil":
                    val_bytes = b"\xFF\x00" if value else b"\x00\x00"
                    data = struct.pack(">H", reg) + val_bytes
                    await self._send_modbus(5, data, slave)
                elif area == "hr":
                    if tag.type == "bool":
                        word = 1 if value else 0
                        data = struct.pack(">HH", reg, word)
                        await self._send_modbus(6, data, slave)
                    elif tag.type in ("int16", "uint16", "byte"):
                        data = struct.pack(">Hh" if tag.type == "int16" else ">HH", reg, int(value))
                        await self._send_modbus(6, data, slave)
                    elif tag.type in ("int32", "uint32", "real"):
                        if tag.type == "real":
                            raw = struct.pack(">f", float(value))
                        elif tag.type == "int32":
                            raw = struct.pack(">i", int(value))
                        else:
                            raw = struct.pack(">I", int(value))
                        data = struct.pack(">HHB", reg, 2, 4) + raw
                        await self._send_modbus(16, data, slave)
            except Exception as exc:
                LOG.warning("Modbus write tag %s failed: %s", tag.id, exc)

    def status(self) -> dict:
        return {
            "state": "connected" if self.connected else "error",
            "message": "" if self.connected else (self.last_error or "Modbus TCP 未连接"),
            "target": f"{self.ip}:{self.port}",
            "protocol": "modbus-tcp"
        }

    async def close(self):
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass


class ModbusRtuBackend(BaseProtocolBackend):
    name = "modbus-rtu"

    def __init__(self, manifest: Manifest, cfg: dict):
        self.manifest = manifest
        self.port = str(cfg.get("port") or manifest.plc.get("port", "/dev/ttyUSB0"))
        self.baudrate = int(cfg.get("baudrate") or manifest.plc.get("baudrate", 9600))
        self.slave_id = int(cfg.get("slaveId") or manifest.plc.get("slaveId", 1))
        self.serial = None
        self.connected = False
        self.last_error = ""
        self.lock = asyncio.Lock()

    async def ensure_connected(self) -> bool:
        if self.connected and self.serial and getattr(self.serial, "is_open", False):
            return True
        try:
            import serial
        except ImportError:
            self.last_error = "缺少 pyserial 模块，请运行 pip install pyserial"
            return False
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1.0)
            self.connected = True
            self.last_error = ""
            LOG.info("Modbus RTU (RS-485) connected on %s @ %d bps", self.port, self.baudrate)
        except Exception as exc:
            self.connected = False
            self.last_error = f"串口打开失败 ({self.port}): {exc}"
            LOG.warning("串口连接失败: %s", exc)
        return self.connected

    async def read_all(self) -> dict[str, Any]:
        if not await self.ensure_connected():
            raise RuntimeError(self.last_error or "Modbus RTU 串口未连接")
        return {}

    async def write(self, tag: Tag, value: Any) -> None:
        if not await self.ensure_connected():
            raise RuntimeError(self.last_error or "Modbus RTU 串口未连接")
        pass

    def status(self) -> dict:
        return {
            "state": "connected" if self.connected else "error",
            "message": "" if self.connected else (self.last_error or "Modbus RTU 未连接"),
            "target": f"{self.port}@{self.baudrate}",
            "protocol": "modbus-rtu"
        }

    async def close(self):
        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass


class TcpRawBackend(BaseProtocolBackend):
    name = "tcp-raw"

    def __init__(self, manifest: Manifest, cfg: dict):
        self.manifest = manifest
        self.ip = str(cfg.get("ip") or manifest.plc.get("ip", "127.0.0.1"))
        self.port = int(cfg.get("port") or manifest.plc.get("port", 8080))
        self.reader = None
        self.writer = None
        self.connected = False
        self.last_error = ""
        self.last_connect_try = 0.0
        self.latest_buffer = bytearray(256)
        self.lock = asyncio.Lock()

    async def ensure_connected(self) -> bool:
        if self.connected and self.writer and not self.writer.is_closing():
            return True
        now = time.monotonic()
        if now - self.last_connect_try < 2.0:
            return False
        self.last_connect_try = now
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port), timeout=3.0
            )
            self.connected = True
            self.last_error = ""
            LOG.info("TCP Raw connected to %s:%d", self.ip, self.port)
        except Exception as exc:
            self.connected = False
            self.last_error = f"TCP Raw 连接失败: {exc}"
            LOG.warning("TCP Raw 连接失败 (%s:%d): %s", self.ip, self.port, exc)
            if self.writer:
                try:
                    self.writer.close()
                except Exception:
                    pass
        return self.connected

    async def read_all(self) -> dict[str, Any]:
        if not await self.ensure_connected():
            raise RuntimeError(self.last_error or "TCP Raw 未连接")
        try:
            chunk = await asyncio.wait_for(self.reader.read(1024), timeout=0.05)
            if chunk:
                self.latest_buffer[:len(chunk)] = chunk
        except asyncio.TimeoutError:
            pass

        out = {}
        for t in self.manifest.tags.values():
            if not t.readable:
                continue
            o = t.byte
            if o + t.size <= len(self.latest_buffer):
                if t.type == "bool":
                    bit = t.bit if t.bit is not None else 0
                    out[t.id] = bool((self.latest_buffer[o] >> bit) & 1)
                elif t.type == "byte":
                    out[t.id] = self.latest_buffer[o]
                elif t.type == "int16":
                    out[t.id] = struct.unpack(">h", self.latest_buffer[o:o+2])[0]
                elif t.type == "uint16":
                    out[t.id] = struct.unpack(">H", self.latest_buffer[o:o+2])[0]
                elif t.type == "real":
                    out[t.id] = round(struct.unpack(">f", self.latest_buffer[o:o+4])[0], 4)
        return out

    async def write(self, tag: Tag, value: Any) -> None:
        if not await self.ensure_connected():
            raise RuntimeError(self.last_error or "TCP Raw 未连接")
        payload = f"{tag.id}={value}\n".encode("utf-8")
        self.writer.write(payload)
        await self.writer.drain()

    def status(self) -> dict:
        return {
            "state": "connected" if self.connected else "error",
            "message": "" if self.connected else (self.last_error or "TCP Raw 未连接"),
            "target": f"{self.ip}:{self.port}",
            "protocol": "tcp-raw"
        }

    async def close(self):
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
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


def create_backend(manifest: Manifest, plc_cfg: dict, mock: bool = False, wait_plc: bool = False):
    if mock:
        return MockBackend(manifest)
    if wait_plc:
        return PendingBackend()

    protocol = str(plc_cfg.get("protocol") or manifest.protocol).lower()
    if protocol in ("s7", "s7comm", "siemens"):
        return S7Backend(manifest, plc_cfg)
    elif protocol in ("modbus-tcp", "modbus_tcp", "modbus"):
        return ModbusTcpBackend(manifest, plc_cfg)
    elif protocol in ("modbus-rtu", "modbus_rtu", "rs485"):
        return ModbusRtuBackend(manifest, plc_cfg)
    elif protocol in ("tcp-raw", "raw-tcp", "tcp", "socket"):
        return TcpRawBackend(manifest, plc_cfg)
    else:
        # 尝试动态加载用户自定义协议驱动模块 custom_driver.py
        try:
            import custom_driver
            if hasattr(custom_driver, "CustomBackend"):
                return custom_driver.CustomBackend(manifest, plc_cfg)
        except ImportError:
            pass
        raise ValueError(
            f"未知的协议类型: {protocol}。目前内置支持: s7, modbus-tcp, modbus-rtu, tcp-raw。"
            f"AI 自主开发新协议驱动请遵循 references/protocol-extension-guide.md 规范。"
        )


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
            elif mtype in ("set_rate", "rate.set", "poll.rate"):
                hz = int(msg.get("pollHz", 10))
                if 1 <= hz <= 50:
                    self.poll_hz = hz
                    LOG.info("Polling rate updated: %d Hz (interval %d ms)", hz, int(1000 / hz))
                    await self._broadcast({"type": "rate_changed", "pollHz": self.poll_hz, "intervalMs": int(1000 / self.poll_hz)})
                    await self._send(websocket, {"type": "ack", "id": mid, "ok": True, "pollHz": self.poll_hz, "intervalMs": int(1000 / self.poll_hz)})
                else:
                    raise ProtocolError("BAD_VALUE", f"pollHz 必须在 1..50 之间，收到: {hz}")
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
        proto = str(msg.get("protocol") or self.manifest.protocol).lower()
        ip = msg.get("ip")
        if proto in ("s7", "s7comm", "siemens", "modbus-tcp", "tcp-raw"):
            try:
                if not isinstance(ipaddress.ip_address(str(ip)), ipaddress.IPv4Address):
                    raise ValueError
            except ValueError:
                raise ProtocolError("BAD_VALUE", "PLC IP 地址格式不正确")
        rack = int(msg.get("rack", 0))
        slot = int(msg.get("slot", 1))
        if "pollHz" in msg:
            try:
                hz = int(msg["pollHz"])
                if 1 <= hz <= 50:
                    self.poll_hz = hz
            except (ValueError, TypeError):
                pass
        plc_cfg = dict(msg)
        plc_cfg["protocol"] = proto
        if ip:
            plc_cfg["ip"] = str(ip)
        plc_cfg["rack"] = rack
        plc_cfg["slot"] = slot
        new_backend = create_backend(self.manifest, plc_cfg)
        async with self.backend_lock:
            old = self.backend
            self.backend = new_backend
            self.latest = {}
            self.last_status = None
            try:
                await old.close()
            except Exception:
                pass
        LOG.info("Target configured: %s proto=%s pollHz=%s", ip or plc_cfg.get("port"), proto, self.poll_hz)
        await self._broadcast({"type": "status", "plc": "waiting",
                               "message": f"正在连接目标设备 ({proto})…", "ts": time.time()})
        await self._send(websocket, {"type": "ack", "id": mid, "ok": True,
                                     "plc": plc_cfg, "pollHz": self.poll_hz})

    def _require_tag(self, tid) -> Tag:
        if not isinstance(tid, str) or tid not in self.manifest.tags:
            raise ProtocolError("BAD_TAG", f"未知 tag: {tid}")
        return self.manifest.tags[tid]

    async def poll_loop(self):
        while True:
            interval = 1.0 / max(1, self.poll_hz)
            t0 = time.monotonic()
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
            elapsed = time.monotonic() - t0
            sleep_time = max(0.002, interval - elapsed)
            await asyncio.sleep(sleep_time)

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
    ap = argparse.ArgumentParser(description="TIA Web Twin 工业协议通信网关")
    ap.add_argument("--config", default="gateway.config.json")
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--mock", action="store_true", help="不连真实设备，使用内存 mock")
    ap.add_argument("--wait-plc", action="store_true", help="启动时等待页面输入 PLC 地址")
    ap.add_argument("--protocol", default=None, help="覆盖协议类型 (s7 / modbus-tcp / modbus-rtu / tcp-raw)")
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
    if args.protocol:
        plc["protocol"] = args.protocol
    if args.plc_ip:
        plc["ip"] = args.plc_ip
    if args.rack is not None:
        plc["rack"] = args.rack
    if args.slot is not None:
        plc["slot"] = args.slot

    backend = create_backend(manifest, plc, mock=mock, wait_plc=args.wait_plc)

    if mock:
        LOG.info("mode=mock (无硬件连接)")
    elif args.wait_plc:
        LOG.info("mode=waiting for target address")
    else:
        target_info = getattr(backend, "ip", getattr(backend, "port", plc.get("ip", "configured")))
        LOG.info("mode=%s target=%s protocol=%s", backend.name, target_info, getattr(backend, "name", "unknown"))
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
