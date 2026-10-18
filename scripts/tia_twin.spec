# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

datas = []
for name in ("index.html", "styles.css", "app.js", "tia-twin-client.js",
             "twin.manifest.json", "gateway.config.json"):
    if os.path.exists(name):
        datas.append((name, "."))
if os.path.isdir("vendor"):
    datas.append(("vendor", "vendor"))

snap_datas, snap_bins, snap_hidden = collect_all("snap7")
datas += snap_datas
hiddenimports = list(snap_hidden) + ["tia_gateway"]

a = Analysis(
    ["desktop_app.py"],
    pathex=[os.getcwd()],
    binaries=snap_bins,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TIAWebTwin",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
