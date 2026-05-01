#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv was not found."
  echo "This evaluator uses uv to create an isolated Python environment."
  read -r -p "Install uv now? [Y/n]: " INSTALL_UV
  if [[ "${INSTALL_UV:-Y}" =~ ^[Nn]$ ]]; then
    echo "Please install uv from https://docs.astral.sh/uv/getting-started/installation/"
    read -r -p "Press Enter to exit..."
    exit 1
  fi
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

uv run --with "pydantic>=2.7" --with "python-dotenv>=1.0" python run_expert_eval.py

read -r -p "Evaluation finished. Press Enter to close..."
