#!/bin/sh
set -eu

/venv/bin/python3 -m geo_processes.startup --config "$PYGEOAPI_CONFIG"
/venv/bin/python3 -m geo_processes.openapi --config "$PYGEOAPI_CONFIG" --output "$PYGEOAPI_OPENAPI"

exec /venv/bin/gunicorn \
    --bind "0.0.0.0:${CONTAINER_PORT:-8080}" \
    --workers "${WSGI_WORKERS:-2}" \
    --worker-class sync \
    --timeout "${WSGI_WORKER_TIMEOUT:-30}" \
    --worker-tmp-dir /tmp \
    "${WSGI_APP:-geo_processes.app:APP}"
