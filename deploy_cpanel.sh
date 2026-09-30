#!/usr/bin/env bash
# Run from the backend folder on the cPanel server.
set -o errexit

if [ -z "$PYTHON" ]; then
  if [ -x .venv/bin/python ]; then
    PYTHON=.venv/bin/python
  else
    PYTHON="$HOME/python312/python/bin/python3.12"
  fi
fi
echo "Using $PYTHON ($("$PYTHON" --version))"

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt
"$PYTHON" manage.py collectstatic --no-input
"$PYTHON" manage.py migrate --no-input

mkdir -p tmp
touch tmp/restart.txt
echo "Deploy complete. Passenger will reload the app on the next request."
