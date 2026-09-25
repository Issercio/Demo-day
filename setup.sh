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

ensure_secret() {
  local file="$1"
  local key="$2"
  local current
  current="$(grep -E "^${key}=" "$file" 2>/dev/null | head -n1 | cut -d= -f2- || true)"
  case "$current" in
    ''|change-me*|florashop-dev-secret-key-min-32-chars)
      local generated
      generated="$(openssl rand -hex 32)"
      if grep -qE "^${key}=" "$file"; then
        sed -i "s|^${key}=.*|${key}=${generated}|" "$file"
      else
        printf '\n%s=%s\n' "$key" "$generated" >> "$file"
      fi
      echo "Generated ${key} in ${file}"
      ;;
  esac
}

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$ROOT/.env.example" "$APP_DIR/.env"
  echo "Created $APP_DIR/.env from .env.example"
fi
ensure_secret "$APP_DIR/.env" SECRET_KEY
ensure_secret "$APP_DIR/.env" JWT_SECRET_KEY

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
echo "Stripe live:  fill STRIPE_* in Demoday/.env, webhook https://VOTRE_DOMAINE/api/v1/payments/webhook"
echo "SMTP:         fill MAIL_SERVER / MAIL_USER / MAIL_PASSWORD (587 STARTTLS or 465 MAIL_SSL=1)"
echo "SIREN:        empty until the operator types a real one in Admin → Identité"
