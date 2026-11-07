#!/usr/bin/env python3
"""Validate a tia-web-twin manifest before wiring it to a PLC.

Usage: python validate_manifest.py twin.manifest.json
Exit code 0 = valid, 1 = validation errors.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ADDR_RE = re.compile(r"^DB(?P<db>\d+)\.(?P<kind>DBX|DBB|DBW|DBD)(?P<byte>\d+)(?:\.(?P<bit>[0-7]))?$")
ID_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
KIND_FOR_TYPE = {
    "bool": "DBX",
    "byte": "DBB",
    "int16": "DBW",
    "uint16": "DBW",
    "int32": "DBD",
    "uint32": "DBD",
    "real": "DBD",
}
SIZE_FOR_TYPE = {"bool": 1, "byte": 1, "int16": 2, "uint16": 2, "int32": 4, "uint32": 4, "real": 4}
INT_RANGES = {
    "int16": (-32768, 32767),
    "uint16": (0, 65535),
    "int32": (-2147483648, 2147483647),
    "uint32": (0, 4294967295),
}
ACCESS = {"r", "w", "rw"}
WRITE_MODES = {"level", "pulse"}


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


def parse_address(addr: str, protocol: str = "s7"):
    protocol = protocol.lower()
    if protocol in ("s7", "s7comm", "siemens"):
        m = ADDR_RE.match(addr or "")
        if not m:
            raise ValueError("S7 地址格式应为 DBn.DBX/DBB/DBW/DBD 或 I0.0 / Q0.0 / IW64 / QW64 / M0.0 / MW10 等")
        if m.group("db"):
            tdb = int(m.group("db"))
            kind = m.group("dbkind").upper()
            byte = int(m.group("dbbyte"))
            bit = int(m.group("dbbit")) if m.group("dbbit") is not None else None
            area = "DB"
            if kind == "DBX" and bit is None:
                raise ValueError("DB 布尔量地址必须带位号，如 DB1.DBX0.0")
            if kind != "DBX" and bit is not None:
                raise ValueError("DBB/DBW/DBD 地址不能带位号")
        else:
            tdb = 0
            area = m.group("area").upper()
            byte = int(m.group("byte"))
            bit = int(m.group("bit")) if m.group("bit") is not None else None
            raw_kind = (m.group("kind") or "").upper()
            if not raw_kind:
                kind = "X" if bit is not None else "B"
            else:
                kind = raw_kind
        return tdb, area, kind, byte, bit
    elif protocol in ("modbus-tcp", "modbus-rtu", "modbus", "modbus_tcp", "modbus_rtu", "rs485"):
        m = MODBUS_ADDR_RE.match(addr or "")
        if not m:
            raise ValueError("Modbus 地址格式应为 0x0001 / 1x0001 / 3x0001 / 4x0001 或 coil:1 / hr:1 或 5位寄存器号")
        return 0, "MODBUS", "MODBUS", 0, None
    elif protocol in ("tcp-raw", "raw-tcp", "socket"):
        m = RAW_ADDR_RE.match(addr or "")
        if not m:
            raise ValueError("Raw TCP 地址格式应为 offset:0 / byte:0[.bit]")
        return 0, "RAW", "RAW", int(m.group("byte")), None
    else:
        # 自定义协议，只要有地址即可
        if not addr:
            raise ValueError("缺少地址")
        return 0, "CUSTOM", "CUSTOM", 0, None


def check_mock_init(tag, errors):
    v = tag.get("mockInit")
    typ = tag.get("type")
    if v is None:
        return
    if typ == "bool":
        if not isinstance(v, bool):
            errors.append(f"tag {tag.get('id')}: bool 的 mockInit 必须是 true/false")
    elif typ == "real":
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            errors.append(f"tag {tag.get('id')}: real 的 mockInit 必须是数字")
    elif typ in INT_RANGES:
        if isinstance(v, bool) or not isinstance(v, int):
            errors.append(f"tag {tag.get('id')}: {typ} 的 mockInit 必须是整数")
        else:
            lo, hi = INT_RANGES[typ]
            if not lo <= v <= hi:
                errors.append(f"tag {tag.get('id')}: mockInit 超出 {typ} 范围")
    elif typ == "byte":
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255:
            errors.append(f"tag {tag.get('id')}: byte 的 mockInit 必须是 0..255")


def validate(path: Path):
    errors, warnings = [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"无法读取 JSON: {exc}"], []
    if data.get("schema") != "tia-web-twin/manifest@1":
        errors.append("schema 必须是 tia-web-twin/manifest@1")
    if not isinstance(data.get("project"), str) or not data["project"].strip():
        errors.append("缺少 project")
    if not isinstance(data.get("title"), str):
        errors.append("缺少 title")
    plc = data.get("plc") or {}
    if not isinstance(plc, dict):
        errors.append("plc 必须是对象")
        plc = {}
    protocol = str(data.get("protocol") or plc.get("protocol", "s7")).lower()
    if protocol in ("s7", "s7comm", "siemens"):
        ip = plc.get("ip")
        if not isinstance(ip, str) or not re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", ip or ""):
            errors.append("plc.ip 必须是 IPv4 地址")
        rack = plc.get("rack")
        slot = plc.get("slot")
        if not isinstance(rack, int) or not 0 <= rack <= 7:
            errors.append("plc.rack 必须是 0..7 的整数")
        if not isinstance(slot, int) or not 0 <= slot <= 31:
            errors.append("plc.slot 必须是 0..31 的整数")
        dbno = plc.get("db")
        if dbno is not None and (not isinstance(dbno, int) or dbno <= 0):
            errors.append("plc.db 若指定必须是大于 0 的整数")
    elif protocol in ("modbus-tcp", "tcp-raw", "raw-tcp", "socket"):
        ip = plc.get("ip")
        if not isinstance(ip, str):
            errors.append("plc.ip 必须是有效 IP 或主机名")
    elif protocol in ("modbus-rtu", "rs485"):
        port = plc.get("port")
        if not isinstance(port, str):
            errors.append("plc.port 必须指定串口设备，如 COM3 或 /dev/ttyUSB0")
    poll = plc.get("defaultPollHz", 10)
    if not isinstance(poll, int) or not 1 <= poll <= 30:
        errors.append("plc.defaultPollHz 必须在 1..30")
    tags = data.get("tags")
    if not isinstance(tags, list) or not tags:
        return errors + ["tags 必须是非空数组"], warnings
    ids, addrs = set(), set()
    intervals_by_db, bool_bytes_by_db, byte_access_by_db = {}, {}, {}
    writable = readable = 0
    parsed = []
    for i, tag in enumerate(tags):
        if not isinstance(tag, dict):
            errors.append(f"tags[{i}] 必须是对象")
            continue
        tid = tag.get("id")
        label = tid or f"tags[{i}]"
        if not isinstance(tid, str) or not ID_RE.match(tid):
            errors.append(f"{label}: id 必须是小写点分命名，如 line.running")
        elif tid in ids:
            errors.append(f"{label}: id 重复")
        else:
            ids.add(tid)
        typ = tag.get("type")
        if typ not in KIND_FOR_TYPE:
            errors.append(f"{label}: type 必须是 {', '.join(KIND_FOR_TYPE)}")
            continue
        access = tag.get("access")
        if access not in ACCESS:
            errors.append(f"{label}: access 必须是 r/w/rw")
        else:
            readable += access in ("r", "rw")
            writable += access in ("w", "rw")
        mode = tag.get("writeMode", "level")
        if mode not in WRITE_MODES:
            errors.append(f"{label}: writeMode 必须是 level/pulse")
        if mode == "pulse" and typ != "bool":
            errors.append(f"{label}: pulse 只支持 bool")
        if mode == "pulse" and access == "r":
            warnings.append(f"{label}: 只读 tag 的 writeMode=pulse 没有意义")
        pulse_ms = tag.get("pulseMs", 150)
        if not isinstance(pulse_ms, int) or not 50 <= pulse_ms <= 2000:
            errors.append(f"{label}: pulseMs 必须在 50..2000")
        addr = tag.get("address")
        if not isinstance(addr, str):
            errors.append(f"{label}: 缺少 address")
            continue
        if addr in addrs:
            errors.append(f"{label}: address 重复 ({addr})")
        addrs.add(addr)
        try:
            tdb, area, kind, byte, bit = parse_address(addr, protocol)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        if protocol in ("s7", "s7comm", "siemens"):
            if area == "DB":
                if not (1 <= tdb <= 65535):
                    errors.append(f"{label}: DB 号必须在 1..65535 之间，发现 DB{tdb}")
                if kind != KIND_FOR_TYPE[typ]:
                    errors.append(f"{label}: {typ} 应使用 {KIND_FOR_TYPE[typ]}，地址是 {kind}")
                if kind in ("DBW", "DBD") and byte % 2:
                    errors.append(f"{label}: {kind} 偏移 {byte} 不是 2 字节对齐")
                if kind == "DBD" and byte % 4:
                    errors.append(f"{label}: DBD 偏移 {byte} 不是 4 字节对齐")
            else:
                if typ == "bool" and bit is None:
                    errors.append(f"{label}: {area} 布尔量地址必须带位号，如 {area}0.0")
                if typ in ("int16", "uint16") and byte % 2:
                    errors.append(f"{label}: {area}W{byte} 必须 2 字节对齐")
                if typ in ("int32", "uint32", "real") and byte % 2:
                    errors.append(f"{label}: {area}D{byte} 必须偶数字节对齐")

            size = SIZE_FOR_TYPE[typ]
            area_key = f"{area}{tdb}" if area == "DB" else area
            byte_access_by_db.setdefault(area_key, {}).setdefault(byte, []).append((label, access))
            if typ == "bool":
                bool_bytes_by_db.setdefault(area_key, []).append(byte)
            else:
                intervals_by_db.setdefault(area_key, []).append((byte, byte + size, label))
        check_mock_init(tag, errors)
        parsed.append((tid or label, addr, typ, access, mode, tag.get("desc", "")))
    if readable == 0:
        errors.append("至少需要一个可读 tag (access=r/rw)")
    if writable == 0:
        warnings.append("没有可写 tag，网页只能看不能操作")
    # 粗粒度重叠检查：按区域 (DB/I/Q/M) 分组检查标量区间不能互相重叠，也不能与布尔位所在字节重叠
    for d, ivs in intervals_by_db.items():
        occupied = {}
        for start, end, label in ivs:
            for b in range(start, end):
                if b in occupied:
                    errors.append(f"{d} {label}: 字节 {b} 与 {occupied[b]} 重叠")
                else:
                    occupied[b] = label
        for b in sorted(set(bool_bytes_by_db.get(d, []))):
            if b in occupied:
                errors.append(f"{d} 布尔位所在字节 {b} 与标量 {occupied[b]} 重叠")
    # 读写字节隔离检查：同一字节内混排 r（只读）与 w/rw（写入）可能发生 S7comm 读改写覆盖风险
    for d, bytes_map in byte_access_by_db.items():
        for b, items in bytes_map.items():
            r_items = [lbl for lbl, acc in items if acc == "r"]
            w_items = [lbl for lbl, acc in items if acc in ("w", "rw")]
            if r_items and w_items:
                warnings.append(
                    f"{d} 字节 {b} 读写混排：该字节同时包含只读位 ({', '.join(r_items)}) 与写入位 ({', '.join(w_items)})。"
                    f"工业最佳实践建议读写字节隔离，避免位写入发生 Read-Modify-Write 覆盖。"
                )
    bindings = data.get("bindings")
    if not isinstance(bindings, list) or not bindings:
        errors.append("bindings 必须是非空数组")
    else:
        seen = set()
        for i, b in enumerate(bindings):
            if not isinstance(b, dict):
                errors.append(f"bindings[{i}] 必须是对象")
                continue
            obj, prop, tid = b.get("object"), b.get("property"), b.get("tag")
            if not all(isinstance(x, str) and x for x in (obj, prop, tid)):
                errors.append(f"bindings[{i}] 需要 object/property/tag")
                continue
            key = (obj, prop)
            if key in seen:
                errors.append(f"binding {obj}.{prop} 重复")
            seen.add(key)
            if tid not in ids:
                errors.append(f"binding {obj}.{prop} 引用了不存在的 tag {tid}")
    if parsed:
        print(f"manifest: {data.get('project')}  ({path})")
        area_labels = []
        dbs_found = sorted(set(
            int(r[1].split('.')[0][2:])
            for r in parsed
            if r[1].upper().startswith('DB') and '.' in r[1] and r[1].split('.')[0][2:].isdigit()
        ))
        if dbs_found:
            area_labels.append(", ".join(f"DB{d}" for d in dbs_found))
        native_areas = sorted(set(
            r[1][0].upper()
            for r in parsed
            if r[1] and r[1][0].upper() in ('I', 'Q', 'M')
        ))
        if native_areas:
            area_labels.append(f"Native: {', '.join(native_areas)}")
        summary_str = "  ".join(area_labels) if area_labels else f"Protocol: {protocol}"
        plc_target = ip or plc.get("port") or "localhost"
        print(f"PLC: {plc_target}  rack={rack} slot={slot}  {summary_str}  poll={poll} Hz")
        print(f"{'ID':<18} {'ADDRESS':<16} {'TYPE':<8} {'ACCESS':<7} {'MODE':<6} DESC")
        for row in parsed:
            print(f"{row[0]:<18} {row[1]:<16} {row[2]:<8} {row[3]:<7} {row[4]:<6} {row[5]}")
        print(f"tags={len(tags)}  readable={readable}  writable={writable}  bindings={len(bindings) if isinstance(bindings, list) else 0}")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print("OK" if not errors else f"FAILED ({len(errors)} errors)")
    return errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", nargs="?", default="twin.manifest.json")
    args = ap.parse_args()
    errors, _ = validate(Path(args.manifest))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
