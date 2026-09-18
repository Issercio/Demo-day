#!/usr/bin/env bash
# Start the FloraShop Flask server on http://0.0.0.0:5000
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$ROOT/Demoday"

if [[ ! -d "$APP_DIR/.venv" ]]; then
  echo "Virtualenv missing. Run ./setup.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source "$APP_DIR/.venv/bin/activate"
cd "$APP_DIR"
exec python run.py
