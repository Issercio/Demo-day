#!/usr/bin/env bash
# Start the shop on https://127.0.0.1:5000 (self-signed cert from ./setup.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$ROOT/Demoday"
CERT="$APP_DIR/certs/localhost.pem"
KEY="$APP_DIR/certs/localhost-key.pem"

if [[ ! -d "$APP_DIR/.venv" ]]; then
  echo "Virtualenv missing. Run ./setup.sh first."
  exit 1
fi

if [[ ! -f "$CERT" || ! -f "$KEY" ]]; then
  echo "TLS files missing. Run ./setup.sh to generate Demoday/certs/."
  exit 1
fi

# shellcheck disable=SC1091
source "$APP_DIR/.venv/bin/activate"
cd "$APP_DIR"
export FLASK_HTTPS=1
export SSL_CERT_FILE="$CERT"
export SSL_KEY_FILE="$KEY"
echo "HTTPS demo: https://127.0.0.1:5000  (accept the self-signed warning once)"
exec python run.py
