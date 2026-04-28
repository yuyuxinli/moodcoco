#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RUNNER_PATH="expert-eval/runner.py"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "未找到 Python 解释器。请先安装 Python 3。"
  read -r -p "按回车退出..."
  exit 1
fi

"$PYTHON_BIN" "$RUNNER_PATH"

read -r -p "评测程序已退出，按回车关闭窗口..."
