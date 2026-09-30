#!/usr/bin/env bash
# Run from the backend folder on the cPanel server with the app's virtualenv activated.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input

mkdir -p tmp
touch tmp/restart.txt
echo "Deploy complete. Passenger will reload the app on the next request."
