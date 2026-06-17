#!/usr/bin/env sh
set -eu

export PYTHONUTF8="${PYTHONUTF8:-1}"
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
export API__PORT="${PORT:-${API__PORT:-5300}}"

if [ -z "${API__WEBHOOK_PREFIX:-}" ]; then
  if [ -n "${RENDER_EXTERNAL_URL:-}" ]; then
    export API__WEBHOOK_PREFIX="$RENDER_EXTERNAL_URL"
  elif [ -n "${RENDER_EXTERNAL_HOSTNAME:-}" ]; then
    export API__WEBHOOK_PREFIX="https://${RENDER_EXTERNAL_HOSTNAME}"
  fi
fi

mkdir -p /app/data/metadata /app/data/logs /app/data/labels /app/data/storage /app/data/chroma /app/data/temp

if [ ! -f /app/data/langbot.db ] && [ -n "${LANGBOT_SEED_DATA_URL:-}" ]; then
  seed_zip="/tmp/langbot-render-data.zip"
  seed_dir="/tmp/langbot-render-seed"

  rm -rf "$seed_dir"
  mkdir -p "$seed_dir"

  echo "Downloading Render seed data..."
  curl -fsSL "$LANGBOT_SEED_DATA_URL" -o "$seed_zip"
  unzip -q "$seed_zip" -d "$seed_dir"

  if [ -f "$seed_dir/langbot.db" ]; then
    cp -a "$seed_dir"/. /app/data/
  elif [ -f "$seed_dir/data/langbot.db" ]; then
    cp -a "$seed_dir/data"/. /app/data/
  else
    echo "LANGBOT_SEED_DATA_URL did not contain langbot.db or data/langbot.db" >&2
    exit 1
  fi
fi

if [ "${LANGBOT_POSTGRES_SEED_FROM_SQLITE:-0}" = "1" ] && [ -n "${DATABASE_URL:-}" ]; then
  if [ -f /app/data/langbot.db ]; then
    echo "Seeding PostgreSQL from SQLite database if target is empty..."
    uv run --no-sync python scripts/sync_sqlite_to_postgres.py --sqlite /app/data/langbot.db
  else
    echo "LANGBOT_POSTGRES_SEED_FROM_SQLITE=1 but /app/data/langbot.db was not found; skipping seed." >&2
  fi
fi

exec uv run --no-sync main.py
