#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v conda >/dev/null 2>&1; then
  eval "$(conda shell.bash hook)"
  conda activate py39
fi

python app.py
