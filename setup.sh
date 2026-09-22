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

CERT_DIR="$APP_DIR/certs"
mkdir -p "$CERT_DIR"
if [[ ! -f "$CERT_DIR/localhost.pem" || ! -f "$CERT_DIR/localhost-key.pem" ]]; then
  openssl req -x509 -newkey rsa:2048 -sha256 -nodes \
    -keyout "$CERT_DIR/localhost-key.pem" \
    -out "$CERT_DIR/localhost.pem" \
    -days 365 \
    -subj "/CN=localhost" \
    >/dev/null 2>&1
  chmod 600 "$CERT_DIR/localhost-key.pem"
  echo "Generated self-signed TLS cert in $CERT_DIR (gitignored)."
fi

(
  cd "$APP_DIR"
  python init_db.py
)

echo
echo "Installation complete."
echo "Launch:       ./run.sh"
echo "Launch HTTPS: ./run-https.sh"
echo "Tests:        ./run-tests.sh"
