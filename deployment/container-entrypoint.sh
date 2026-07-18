#!/bin/sh
set -eu

: "${FORCE_SCRIPT_NAME:=/labhub}"
: "${LABHUB_LICENSE_ENFORCED:=True}"
: "${PORT:=8000}"

export FORCE_SCRIPT_NAME LABHUB_LICENSE_ENFORCED PORT

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec python -m daphne -b 0.0.0.0 -p "$PORT" project_laboran.asgi:application
