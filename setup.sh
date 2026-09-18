#!/usr/bin/env bash
# Install Python dependencies and prepare a local .env for FloraShop.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$ROOT/Demoday"

python3 -m venv "$APP_DIR/.venv"
# shellcheck disable=SC1091
source "$APP_DIR/.venv/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$ROOT/.env.example" "$APP_DIR/.env"
  echo "Created $APP_DIR/.env from .env.example (edit secrets before production)."
fi

(
  cd "$APP_DIR"
  python init_db.py
)

echo
echo "Installation complete."
echo "Launch:  ./run.sh"
echo "Tests:   ./run-tests.sh"
