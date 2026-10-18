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


def parse_address(addr: str):
    m = ADDR_RE.match(addr or "")
    if not m:
        raise ValueError("地址格式应为 DBn.DBX/DBB/DBW/DBD<offset>[.bit]")
    kind = m.group("kind")
    byte = int(m.group("byte"))
    bit = int(m.group("bit")) if m.group("bit") is not None else None
    if kind == "DBX" and bit is None:
        raise ValueError("布尔量地址必须带位号，如 DB1.DBX0.0")
    if kind != "DBX" and bit is not None:
        raise ValueError("DBB/DBW/DBD 地址不能带位号")
    return int(m.group("db")), kind, byte, bit


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
    poll = plc.get("defaultPollHz", 10)
    if not isinstance(poll, int) or not 1 <= poll <= 30:
        errors.append("plc.defaultPollHz 必须在 1..30")
    tags = data.get("tags")
    if not isinstance(tags, list) or not tags:
        return errors + ["tags 必须是非空数组"], warnings
    ids, addrs = set(), set()
    intervals_by_db, bool_bytes_by_db = {}, {}
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
            tdb, kind, byte, bit = parse_address(addr)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        if not (1 <= tdb <= 65535):
            errors.append(f"{label}: DB 号必须在 1..65535 之间，发现 DB{tdb}")
        if kind != KIND_FOR_TYPE[typ]:
            errors.append(f"{label}: {typ} 应使用 {KIND_FOR_TYPE[typ]}，地址是 {kind}")
        if kind in ("DBW", "DBD") and byte % 2:
            errors.append(f"{label}: {kind} 偏移 {byte} 不是 2 字节对齐")
        if kind == "DBD" and byte % 4:
            errors.append(f"{label}: DBD 偏移 {byte} 不是 4 字节对齐")
        size = SIZE_FOR_TYPE[typ]
        if kind == "DBX":
            bool_bytes_by_db.setdefault(tdb, []).append(byte)
        else:
            intervals_by_db.setdefault(tdb, []).append((byte, byte + size, label))
        check_mock_init(tag, errors)
        parsed.append((tid or label, addr, typ, access, mode, tag.get("desc", "")))
    if readable == 0:
        errors.append("至少需要一个可读 tag (access=r/rw)")
    if writable == 0:
        warnings.append("没有可写 tag，网页只能看不能操作")
    # 粗粒度重叠检查：按 DB 分组检查标量区间不能互相重叠，也不能与布尔位所在字节重叠
    for d, ivs in intervals_by_db.items():
        occupied = {}
        for start, end, label in ivs:
            for b in range(start, end):
                if b in occupied:
                    errors.append(f"DB{d} {label}: 字节 {b} 与 {occupied[b]} 重叠")
                else:
                    occupied[b] = label
        for b in sorted(set(bool_bytes_by_db.get(d, []))):
            if b in occupied:
                errors.append(f"DB{d} 布尔位所在字节 {b} 与标量 {occupied[b]} 重叠")
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
        dbs_found = sorted(set(int(r[1].split('.')[0].replace('DB', '')) for r in parsed))
        dbs_str = ", ".join(f"DB{d}" for d in dbs_found)
        print(f"PLC: {ip}  rack={rack} slot={slot}  {dbs_str}  poll={poll} Hz")
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
