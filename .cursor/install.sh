#!/usr/bin/env bash
# Idempotent dependency + database bootstrap for the FloraShop (Demo-day) app.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

# System packages. Normally already present from the base snapshot; guarded so a
# fresh image also works.
if ! dpkg -s postgresql >/dev/null 2>&1; then
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    postgresql postgresql-contrib python3-venv python3-dev libpq-dev build-essential
fi

cd "${REPO_ROOT}/Demoday"

# Python virtual environment + dependencies.
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Local configuration.
[ -f .env ] || cp .env.example .env

# Database: start PostgreSQL, then (re)create schema, admin user and seed catalog.
bash "${REPO_ROOT}/.cursor/pg-up.sh"
python3 init_db.py
python3 seed_data.py

echo "Install complete."
