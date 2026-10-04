#!/bin/sh
# Har start par wahi jo build.sh Render par karta tha: migrate aur seed.
# seed_booking_mvp idempotent hai — catalog pehle se ho to sirf kami poori karta hai.
set -e
python manage.py migrate --no-input
python manage.py seed_booking_mvp
exec "$@"
