#!/usr/bin/env bash
# Bring up the local PostgreSQL 16 cluster and ensure the florashop role/database
# exist. Idempotent and returns once the server is accepting connections.
set -euo pipefail

PG_VERSION=16
PGBIN="/usr/lib/postgresql/${PG_VERSION}/bin"
PGDATA="/var/lib/postgresql/${PG_VERSION}/main"
PGCONF="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"

sudo mkdir -p /var/run/postgresql
sudo chown postgres:postgres /var/run/postgresql

if ! sudo -u postgres "${PGBIN}/pg_ctl" -D "${PGDATA}" status >/dev/null 2>&1; then
  sudo -u postgres "${PGBIN}/pg_ctl" -D "${PGDATA}" \
    -o "-c config_file=${PGCONF}" \
    -l /tmp/postgresql.log -w start
fi

# Wait until the server accepts connections.
for _ in $(seq 1 30); do
  if sudo -u postgres "${PGBIN}/pg_isready" -q; then
    break
  fi
  sleep 1
done

sudo -u postgres psql -v ON_ERROR_STOP=1 -c "ALTER USER postgres WITH PASSWORD 'root';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='florashop'" \
  | grep -q 1 || sudo -u postgres createdb florashop

echo "PostgreSQL is up and 'florashop' database is ready."
