#!/usr/bin/env bash
# Run the automated test suite.
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
export DATABASE_URL="${DATABASE_URL:-sqlite://}"
export STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}"
export STRIPE_PUBLISHABLE_KEY="${STRIPE_PUBLISHABLE_KEY:-}"

python -m coverage run --source=app -m unittest discover -s tests -v
python -m coverage report -m
