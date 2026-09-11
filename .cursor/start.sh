#!/usr/bin/env bash
# Per-boot reconciliation: ensure PostgreSQL is running before the app starts.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "${REPO_ROOT}/.cursor/pg-up.sh"
