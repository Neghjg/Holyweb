#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py init_clickhouse
if [ "${SEED_DEMO:-0}" = "1" ]; then
    python manage.py seed_demo
fi

exec "$@"
