#!/bin/sh
set -eu

plugin_pid=""
app_pid=""

cleanup() {
    if [ -n "${app_pid}" ]; then
        kill "${app_pid}" 2>/dev/null || true
    fi
    if [ -n "${plugin_pid}" ]; then
        kill "${plugin_pid}" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
}

trap 'cleanup; exit 143' TERM INT

export PORT="${PORT:-5300}"
export API__PORT="${API__PORT:-$PORT}"
export PLUGIN__RUNTIME_WS_URL="${PLUGIN__RUNTIME_WS_URL:-ws://127.0.0.1:5400/control/ws}"

if [ -n "${RAILWAY_PUBLIC_DOMAIN:-}" ] && [ -z "${API__WEBHOOK_PREFIX:-}" ]; then
    export API__WEBHOOK_PREFIX="https://${RAILWAY_PUBLIC_DOMAIN}"
fi

if [ -n "${RAILWAY_VOLUME_MOUNT_PATH:-}" ] && [ "${RAILWAY_VOLUME_MOUNT_PATH}" != "/app/data" ]; then
    mkdir -p "${RAILWAY_VOLUME_MOUNT_PATH}"
    if [ ! -e /app/data ]; then
        ln -s "${RAILWAY_VOLUME_MOUNT_PATH}" /app/data
        echo "Linked /app/data to Railway volume at ${RAILWAY_VOLUME_MOUNT_PATH}."
    elif [ -d /app/data ] && [ -z "$(ls -A /app/data 2>/dev/null)" ]; then
        rmdir /app/data
        ln -s "${RAILWAY_VOLUME_MOUNT_PATH}" /app/data
        echo "Linked empty /app/data to Railway volume at ${RAILWAY_VOLUME_MOUNT_PATH}."
    else
        echo "Railway volume is mounted at ${RAILWAY_VOLUME_MOUNT_PATH}; /app/data already exists, so it was not linked." >&2
    fi
fi

if [ -n "${DATABASE_URL:-}" ] && [ -z "${DATABASE__POSTGRESQL__HOST:-}" ]; then
    eval "$(
        python - <<'PY'
import os
import shlex
from urllib.parse import unquote, urlparse

url = urlparse(os.environ["DATABASE_URL"])
database = unquote(url.path.lstrip("/") or "postgres")
values = {
    "DATABASE__USE": "postgresql",
    "DATABASE__POSTGRESQL__HOST": url.hostname or "",
    "DATABASE__POSTGRESQL__PORT": str(url.port or 5432),
    "DATABASE__POSTGRESQL__USER": unquote(url.username or "postgres"),
    "DATABASE__POSTGRESQL__PASSWORD": unquote(url.password or ""),
    "DATABASE__POSTGRESQL__DATABASE": database,
}
for key, value in values.items():
    print(f"export {key}={shlex.quote(value)}")
PY
    )"
fi

echo "Starting LangBot plugin runtime..."
uv run --no-sync -m langbot_plugin.cli.__init__ rt &
plugin_pid="$!"

sleep 2
if ! kill -0 "${plugin_pid}" 2>/dev/null; then
    echo "LangBot plugin runtime exited before the main service started." >&2
    wait "${plugin_pid}" || true
    exit 1
fi

echo "Starting LangBot main service on port ${API__PORT}..."
uv run --no-sync main.py &
app_pid="$!"

while true; do
    if ! kill -0 "${app_pid}" 2>/dev/null; then
        set +e
        wait "${app_pid}"
        status="$?"
        set -e
        cleanup
        exit "${status}"
    fi

    if ! kill -0 "${plugin_pid}" 2>/dev/null; then
        echo "LangBot plugin runtime exited while the main service was running." >&2
        cleanup
        exit 1
    fi

    sleep 5
done
