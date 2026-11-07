#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Siemens S7 Web Twin - 3D 模型 (GLB/glTF) 节点树与机电契约自检工具
Zero-dependency inspection & manifest bindings generator for Blender & CAD exports.

使用方法:
  python inspect_glb.py path/to/model.glb
  python inspect_glb.py path/to/model.glb --generate-bindings
"""

import sys
import json
import struct
import argparse
from pathlib import Path

def parse_glb(file_path: Path) -> dict:
    with open(file_path, "rb") as f:
        data = f.read()

    if len(data) < 12:
        raise ValueError("文件过小，非有效 GLB 文件")

    magic, version, length = struct.unpack("<4sII", data[:12])
    if magic != b"glTF":
        raise ValueError(f"不是合法的 GLB 文件 (Magic: {magic})")

    # 解析第一个 Chunk (必须为 JSON Chunk: 0x4E4F534A)
    offset = 12
    if offset >= len(data):
        raise ValueError("缺少 JSON 数据块")

    chunk_length, chunk_type = struct.unpack("<II", data[offset:offset+8])
    if chunk_type != 0x4E4F534A: # "JSON"
        raise ValueError(f"首个数据块不是 JSON Chunk (Type: {hex(chunk_type)})")

    json_bytes = data[offset+8 : offset+8+chunk_length]
    return json.loads(json_bytes.decode("utf-8"))

def parse_gltf(file_path: Path) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def inspect_model(file_path: Path):
    if not file_path.exists():
        print(f"[错误] 文件不存在: {file_path}", file=sys.stderr)
        sys.exit(1)

    suffix = file_path.suffix.lower()
    if suffix == ".glb":
        gltf_data = parse_glb(file_path)
    elif suffix in (".gltf", ".json"):
        gltf_data = parse_gltf(file_path)
    else:
        print(f"[错误] 不支持的文件扩展名: {suffix} (仅支持 .glb / .gltf)", file=sys.stderr)
        sys.exit(1)

    nodes = gltf_data.get("nodes", [])
    meshes = gltf_data.get("meshes", [])
    scenes = gltf_data.get("scenes", [])
    materials = gltf_data.get("materials", [])
    default_scene_idx = gltf_data.get("scene", 0)

    print("=" * 70)
    print(f"🏭 Siemens S7 Web Twin - 3D 模型资产检查报告: {file_path.name}")
    print("=" * 70)
    print(f"· 场景数: {len(scenes)} | 总节点数: {len(nodes)} | 网格 (Mesh) 数: {len(meshes)} | 材质数: {len(materials)}")
    
    # 建立子节点父子关系
    parent_map = {}
    for idx, node in enumerate(nodes):
        for child_idx in node.get("children", []):
            parent_map[child_idx] = idx

    # 找出根节点
    default_scene = scenes[default_scene_idx] if scenes else {}
    root_nodes = default_scene.get("nodes", [i for i in range(len(nodes)) if i not in parent_map])

    actuator_nodes = []
    sensor_nodes = []
    light_nodes = []
    belt_nodes = []
    static_nodes = []
    suspicious_nodes = []

    def classify_node(name: str):
        lower = name.lower()
        if any(k in lower for k in ["actuator", "pusher", "cylinder", "turntable", "motor", "arm", "lifter"]):
            return "actuator"
        elif any(k in lower for k in ["sensor", "pe", "switch", "photo", "beam"]):
            return "sensor"
        elif any(k in lower for k in ["light", "lamp", "led", "stack", "indicator"]):
            return "light"
        elif any(k in lower for k in ["belt", "conveyor"]):
            return "belt"
        elif any(k in lower for k in ["static", "frame", "base", "stand"]):
            return "static"
        return "other"

    print("\n📂 [节点拓扑层级树]:")
    def print_tree(node_idx: int, indent: int = 0):
        node = nodes[node_idx]
        name = node.get("name", f"Node_{node_idx}")
        has_mesh = "mesh" in node
        category = classify_node(name)
        
        # 标记提示
        tag_str = ""
        if category == "actuator":
            tag_str = " ⚡ [动件执行器]"
            actuator_nodes.append((name, node))
        elif category == "sensor":
            tag_str = " 🎯 [传感器探头]"
            sensor_nodes.append((name, node))
        elif category == "light":
            tag_str = " 💡 [指示灯/材质]"
            light_nodes.append((name, node))
        elif category == "belt":
            tag_str = " 🔄 [输送带表面]"
            belt_nodes.append((name, node))
        elif category == "static":
            tag_str = " 🏛️ [静态基座]"
            static_nodes.append((name, node))
        
        if ".00" in name:
            tag_str += " ⚠️ (警告: 含有 Blender 自动重命名 .001，建议规整命名)"
            suspicious_nodes.append(name)

        # 变换检查
        scale = node.get("scale", [1.0, 1.0, 1.0])
        if any(abs(s - 1.0) > 1e-4 for s in scale):
            tag_str += f" [Scale: {scale} 建议 Blender 内 Ctrl+A 应用缩放]"

        prefix = "  " * indent + ("└─ " if indent > 0 else "")
        mesh_info = f" (Mesh: {meshes[node['mesh']].get('name', node['mesh'])})" if has_mesh else " (Empty/Group)"
        print(f"{prefix}{name}{mesh_info}{tag_str}")

        for child_idx in node.get("children", []):
            print_tree(child_idx, indent + 1)

    for r_idx in root_nodes:
        print_tree(r_idx, 0)

    print("\n" + "=" * 70)
    print("📊 [机电契约构件识别统计]:")
    print(f"  • 识别出动件执行器 (Actuators): {len(actuator_nodes)} 个")
    print(f"  • 识别出传感器检测点 (Sensors):   {len(sensor_nodes)} 个")
    print(f"  • 识别出指示灯/光源 (Lights):     {len(light_nodes)} 个")
    print(f"  • 识别出输送带驱动面 (Belts):     {len(belt_nodes)} 个")
    print(f"  • 识别出静态支撑基座 (Static):    {len(static_nodes)} 个")
    print("=" * 70)

    # 自动生成 twin.manifest.json bindings 片段
    print("\n📋 [自动生成的 twin.manifest.json bindings 推荐模板]:")
    print("/* 将以下 bindings 配置复制到你的 twin.manifest.json 中使用: */")
    
    suggested_bindings = []

    for name, node in actuator_nodes:
        lower = name.lower()
        if "turn" in lower or "motor" in lower:
            suggested_bindings.append({
                "node": name,
                "tag": "motor.turn",
                "type": "rotate",
                "axis": "y",
                "speed": 1.0,
                "desc": f"PLC 驱动 {name} 回转运动"
            })
        else:
            suggested_bindings.append({
                "node": name,
                "tag": "out.cyl",
                "type": "translate",
                "axis": "x",
                "from": 0.0,
                "to": 0.15,
                "durationMs": 200,
                "desc": f"PLC 驱动 {name} 伸缩直线位移 (150mm)"
            })

    for name, node in sensor_nodes:
        suggested_bindings.append({
            "node": name,
            "tag": "sensor.pe1",
            "type": "raycast",
            "direction": [0, -1, 0],
            "length": 0.2,
            "desc": f"从 {name} 探头向下发射 200mm 光电检测射线"
        })

    for name, node in light_nodes:
        suggested_bindings.append({
            "node": name,
            "tag": "stack.green",
            "type": "emissive",
            "onColor": "#00ff33",
            "offColor": "#112211",
            "intensity": 2.0,
            "desc": f"PLC 信号驱动 {name} 材质自发光变色"
        })

    for name, node in belt_nodes:
        suggested_bindings.append({
            "node": name,
            "tag": "line.running",
            "type": "texture_scroll",
            "axis": "y",
            "speed": 0.3,
            "desc": f"输送线运行时驱动 {name} 材质 UV 滚动"
        })

    print(json.dumps(suggested_bindings, ensure_ascii=False, indent=2))
    print("\n💡 提示: 模型文件可在前端直接配合 Three.js GLTFLoader 驱动，无需修改 3D 渲染底层！\n")

def main():
    parser = argparse.ArgumentParser(description="Siemens S7 Web Twin - 3D 模型资产与契约自检工具")
    parser.add_argument("model_file", help="待检查的 .glb 或 .gltf 文件路径")
    args = parser.parse_args()

    inspect_model(Path(args.model_file))

if __name__ == "__main__":
    main()
