#!/usr/bin/env bash
# Double-click launcher: create the local env once, then start page + gateway.
set -u
cd "$(dirname "$0")"
TITLE="TIA Web Twin"
echo "=============================================="
echo "  $TITLE"
echo "  关闭此窗口即停止网页与本地网关"
echo "=============================================="
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 python3。请先安装 Python 3.10+（含 python3-venv）。"
  read -r -p "按回车关闭..." _
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "首次启动：正在创建 Python 环境..."
  python3 -m venv .venv || {
    echo "创建 .venv 失败，请安装 python3-venv 后重试。"
    read -r -p "按回车关闭..." _
    exit 1
  }
  .venv/bin/python -m pip install -r requirements.txt || {
    echo "依赖安装失败，请检查网络或 requirements.txt。"
    read -r -p "按回车关闭..." _
    exit 1
  }
  touch .venv/.deps-ok
elif [ ! -f ".venv/.deps-ok" ]; then
  echo "正在安装依赖..."
  .venv/bin/python -m pip install -r requirements.txt || {
    echo "依赖安装失败。"
    read -r -p "按回车关闭..." _
    exit 1
  }
  touch .venv/.deps-ok
fi

exec .venv/bin/python run_twin.py
