#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
generate_scl.py - 从 twin.manifest.json 自动生成西门子博途 SCL 外部源文件
==============================================================================
用法：
    python generate_scl.py [manifest_path] [output_scl_path]

示例：
    python generate_scl.py ../assets/template/twin.manifest.json ../assets/tia/TwinIO.scl
==============================================================================
"""

import sys
import os
import json
import re

ADDR_RE = re.compile(r"^DB(?P<db>\d+)\.(?P<kind>DBX|DBB|DBW|DBD)(?P<byte>\d+)(?:\.(?P<bit>[0-7]))?$")

TYPE_MAP = {
    "bool": "Bool",
    "byte": "Byte",
    "int16": "Int",
    "uint16": "UInt",
    "int32": "DInt",
    "uint32": "UDInt",
    "real": "Real"
}

SIZE_MAP = {
    "bool": 1, # 1 bit
    "byte": 1,
    "int16": 2,
    "uint16": 2,
    "int32": 4,
    "uint32": 4,
    "real": 4
}


def sanitize_var_name(tag_id: str) -> str:
    return tag_id.replace(".", "_").replace("-", "_")


def generate_scl(manifest_data: dict) -> str:
    plc_cfg = manifest_data.get("plc", {})
    default_db_name = plc_cfg.get("dbName", "TwinIO")
    default_db = plc_cfg.get("db", 1)
    tags = manifest_data.get("tags", [])

    # 解析 tags 并按 db 分组
    by_db = {}
    for t in tags:
        m = ADDR_RE.match(t["address"])
        if not m:
            continue
        db_num = int(m.group("db"))
        kind = m.group("kind")
        byte_idx = int(m.group("byte"))
        bit_idx = int(m.group("bit")) if m.group("bit") is not None else 0
        by_db.setdefault(db_num, []).append({
            "id": t["id"],
            "scl_name": sanitize_var_name(t["id"]),
            "address": t["address"],
            "kind": kind,
            "byte": byte_idx,
            "bit": bit_idx,
            "type": t["type"],
            "desc": t.get("desc", ""),
            "mockInit": t.get("mockInit")
        })

    lines = []
    lines.append("// ==============================================================================")
    lines.append(f"// TIA Portal 外部源文件")
    lines.append(f"// 工程项目: {manifest_data.get('project', 'twin')}")
    lines.append("// 自动生成自: twin.manifest.json (原生支持跨 DB)")
    lines.append("// 说明：此数据块必须关闭【优化的块访问】，以确保固定物理地址对齐。")
    lines.append("// 导入博途：项目树 -> 外部源文件 -> 添加此文件 -> 右键'从源文件生成块'")
    lines.append("// ==============================================================================")
    lines.append("")

    for db_num in sorted(by_db.keys()):
        parsed_tags = by_db[db_num]
        parsed_tags.sort(key=lambda x: (x["byte"], x["bit"]))

        if len(by_db) == 1 and db_num == default_db:
            block_name = default_db_name
        else:
            block_name = f"{default_db_name}_DB{db_num}" if db_num != default_db else default_db_name

        lines.append(f'DATA_BLOCK "{block_name}"')
        lines.append("{ S7_Optimized_Access := 'FALSE' }")
        lines.append("VERSION : 0.1")
        lines.append("NON_RETAIN")
        lines.append("   STRUCT")

        current_byte = 0
        current_bit = 0
        init_assignments = []

        for t in parsed_tags:
            target_byte = t["byte"]
            target_bit = t["bit"]
            t_type = t["type"]

            # 处理字节间跳跃空隙 (Padding)
            if target_byte > current_byte:
                if current_bit > 0:
                    pad_bits_count = 8 - current_bit
                    lines.append(f"      _pad_b{current_byte}_bits : ARRAY[0..{pad_bits_count - 1}] OF Bool; // 填充位")
                    current_byte += 1
                    current_bit = 0

                gap = target_byte - current_byte
                if gap > 0:
                    if gap == 1:
                        lines.append(f"      _pad_b{current_byte} : Byte; // 字节对齐填充")
                    else:
                        lines.append(f"      _pad_b{current_byte}_b{target_byte - 1} : ARRAY[0..{gap - 1}] OF Byte; // 空间填充")
                    current_byte = target_byte

            if t_type == "bool":
                if target_bit > current_bit:
                    gap_bits = target_bit - current_bit
                    lines.append(f"      _pad_b{target_byte}_bit{current_bit}_to_{target_bit - 1} : ARRAY[0..{gap_bits - 1}] OF Bool;")
                    current_bit = target_bit

                scl_type = "Bool"
                lines.append(f"      {t['scl_name']} : {scl_type}; // {t['address']}: {t['desc']}")
                current_bit += 1
                if current_bit >= 8:
                    current_byte += 1
                    current_bit = 0
            else:
                if current_bit > 0:
                    pad_bits_count = 8 - current_bit
                    lines.append(f"      _pad_b{current_byte}_tail_bits : ARRAY[0..{pad_bits_count - 1}] OF Bool;")
                    current_byte += 1
                    current_bit = 0

                scl_type = TYPE_MAP.get(t_type, "DWord")
                lines.append(f"      {t['scl_name']} : {scl_type}; // {t['address']}: {t['desc']}")
                size = SIZE_MAP.get(t_type, 4)
                current_byte += size

            if t["mockInit"] is not None:
                v = t["mockInit"]
                if isinstance(v, bool):
                    init_val = "TRUE" if v else "FALSE"
                elif isinstance(v, float):
                    init_val = f"{v:.2f}"
                else:
                    init_val = str(v)
                init_assignments.append(f"   {t['scl_name']} := {init_val};")

        lines.append("   END_STRUCT;")
        lines.append("")
        lines.append("BEGIN")
        if init_assignments:
            lines.extend(init_assignments)
        lines.append("END_DATA_BLOCK")
        lines.append("")

    return "\n".join(lines)


def main():
    manifest_path = sys.argv[1] if len(sys.argv) > 1 else "twin.manifest.json"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "TwinIO.scl"

    if not os.path.exists(manifest_path):
        print(f"错误: 找不到 {manifest_path}")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    scl_content = generate_scl(data)

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(scl_content)

    print(f"成功生成 SCL 文件: {output_path}")


if __name__ == "__main__":
    main()
