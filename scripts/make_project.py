#!/usr/bin/env python3
"""Scaffold a TIA Web Twin project from the skill template.

Usage:
  python make_project.py --out ./my-line
  python make_project.py --out ./my-line --manifest ./my-line.manifest.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL / "assets" / "template"
RUNTIME = SKILL / "assets" / "runtime" / "tia-twin-client.js"
PORTABLE_RUNTIME_ZIP = SKILL / "assets" / "runtime" / "portable-runtime.zip"
THREE_DEMO = SKILL / "assets" / "three-demo"
SCRIPTS = ["tia_gateway.py", "validate_manifest.py", "generate_scl.py", "run_twin.py", "inspect_glb.py", "requirements.txt"]
LAUNCHERS = [
    "start_twin.sh",
    "start_twin.bat",
    "start.bat",
    "start_silent.bat",
    "stop.bat",
    "make_shortcut.bat",
]
PACKAGING = ["desktop_app.py", "tia_twin.spec", "build_exe.bat"]
TEMPLATE_FILES = ["index.html", "styles.css", "app.js", "twin.manifest.json", "gateway.config.json"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Siemens S7 Web Twin 项目生成脚手架")
    ap.add_argument("--out", required=True, help="目标项目目录")
    ap.add_argument("--manifest", default=None, help="可选：替换模板 manifest")
    ap.add_argument("--force", action="store_true", help="目标目录非空时允许覆盖同名文件")
    ap.add_argument(
        "--mode", "--modeling",
        choices=["html", "blender"],
        default=None,
        dest="mode",
        help="建模方式选择：html (原生网页纯代码生成，零依赖极速) 或 blender (Blender 工业级高保真 3D 资产导出)"
    )
    ap.add_argument(
        "--scene",
        choices=["2d", "3d"],
        default=None,
        help="[兼容旧参数] 2d 对应 html 原生建模，3d 对应 blender 工业建模"
    )
    args = ap.parse_args()

    # 统一解析建模方式：优先使用 --mode，其次兼容 --scene，默认 html
    if args.mode:
        modeling_mode = args.mode
    elif args.scene:
        modeling_mode = "blender" if args.scene == "3d" else "html"
    else:
        modeling_mode = "html"

    out = Path(args.out).expanduser().resolve()
    existing = list(out.iterdir()) if out.exists() else []
    if existing and not args.force:
        print(f"目标目录已存在且非空：{out}\n加 --force 覆盖同名文件（不会删除其他文件）")
        return 2

    # Validate before writing anything.
    manifest_src = Path(args.manifest).expanduser().resolve() if args.manifest else TEMPLATE / "twin.manifest.json"
    if not manifest_src.exists():
        print(f"manifest 不存在：{manifest_src}")
        return 2
    validate = SKILL / "scripts" / "validate_manifest.py"
    check = subprocess.run([sys.executable, str(validate), str(manifest_src)], capture_output=True, text=True)
    if check.returncode != 0:
        print(check.stdout)
        print(check.stderr)
        print("manifest 校验失败，未生成项目。")
        return 1

    out.mkdir(parents=True, exist_ok=True)
    if modeling_mode == "blender":
        shutil.copy2(THREE_DEMO / "index.html", out / "index.html")
        shutil.copy2(THREE_DEMO / "styles.css", out / "styles.css")
        shutil.copy2(THREE_DEMO / "app.js", out / "app.js")
        shutil.copytree(THREE_DEMO / "vendor", out / "vendor", dirs_exist_ok=True)
        # 预先创建用于放置 Blender .glb 模型的目录
        (out / "assets" / "models").mkdir(parents=True, exist_ok=True)
        shutil.copy2(TEMPLATE / "twin.manifest.json", out / "twin.manifest.json")
        shutil.copy2(TEMPLATE / "gateway.config.json", out / "gateway.config.json")
    else:
        for name in TEMPLATE_FILES:
            shutil.copy2(TEMPLATE / name, out / name)
    shutil.copy2(RUNTIME, out / "tia-twin-client.js")
    for name in SCRIPTS:
        shutil.copy2(SKILL / "scripts" / name, out / name)
    for name in LAUNCHERS:
        shutil.copy2(SKILL / "scripts" / name, out / name)
    for name in PACKAGING:
        shutil.copy2(SKILL / "scripts" / name, out / name)
    if PORTABLE_RUNTIME_ZIP.exists():
        import zipfile
        rt_target = out / "runtime"
        if not rt_target.exists():
            print("正在内置免安装绿色 Python 运行时 (runtime/)...")
            rt_target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(PORTABLE_RUNTIME_ZIP, "r") as zf:
                zf.extractall(rt_target)
    try:
        os.chmod(out / "start_twin.sh", 0o755)
    except OSError:
        pass
    desktop = out / "start_twin.desktop"
    exe = str(out / "start_twin.sh").replace("%", "%%")
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=TIA Web Twin\n"
        "Name[zh_CN]=数字孪生启动器\n"
        "Comment=启动数字孪生网页与本地网关\n"
        f'Exec=/bin/bash "{exe}"\n'
        f"Path={out}\n"
        "Terminal=true\n"
        "Icon=utilities-terminal\n"
        "Categories=Development;\n",
        encoding="utf-8",
    )
    try:
        os.chmod(desktop, 0o755)
    except OSError:
        pass
    if manifest_src.resolve() != (TEMPLATE / "twin.manifest.json").resolve():
        shutil.copy2(manifest_src, out / "twin.manifest.json")

    gen = subprocess.run(
        [sys.executable, str(out / "generate_scl.py"), str(out / "twin.manifest.json"), str(out / "TwinIO.scl")],
        capture_output=True, text=True,
    )
    if gen.returncode != 0:
        print(gen.stdout)
        print(gen.stderr)
        print("SCL 生成失败。")
        return 1

    # Keep the gateway pointed at the project-local manifest.
    cfg_path = out / "gateway.config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["manifest"] = "twin.manifest.json"
    m = json.loads((out / "twin.manifest.json").read_text(encoding="utf-8"))
    plc = m.get("plc", {})
    cfg["plc"] = {
        "ip": plc.get("ip", cfg.get("plc", {}).get("ip", "192.168.0.1")),
        "rack": plc.get("rack", 0),
        "slot": plc.get("slot", 1),
    }
    cfg["pollHz"] = plc.get("defaultPollHz", cfg.get("pollHz", 10))
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    mode_desc = "【Blender 工业级建模】" if modeling_mode == "blender" else "【HTML 原生建模】"
    print(f"项目已生成：{out}  ({mode_desc} 模式)")
    if modeling_mode == "blender":
        print("  · 模型放置目录：./assets/models/ (导出 .glb 后放置于此)")
        print("  · 模型自检工具：python inspect_glb.py assets/models/your_line.glb")
    print("\n下一步（零环境门槛交付）：")
    print(f"  打开文件夹：{out}")
    print("  Windows：双击 start.bat 或运行 make_shortcut.bat 创建桌面快捷方式")
    print("  （已内置 20MB 绿色便携 Python 运行时，目标电脑无需安装 Python、无需网络、无需管理员权限）")
    print("  Linux：双击 start_twin.desktop 或运行 ./start_twin.sh")
    print("\n双击脚本会自动拉起后台网关与 3D 页面；页面右上角输入 PLC IP 点击连接即可联调。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
