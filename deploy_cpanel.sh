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
PUBLIC_DIR="${PUBLIC_DIR:-$HOME/faiyaz.brolyticstechnologies.com}"
mkdir -p tmp logs
echo "Using $PYTHON ($("$PYTHON" --version))"

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt
"$PYTHON" manage.py collectstatic --no-input
"$PYTHON" manage.py migrate --no-input

if [ -d "$PUBLIC_DIR" ]; then
  mkdir -p "$PUBLIC_DIR/cgi-bin"
  cp cpanel/bromade.cgi "$PUBLIC_DIR/cgi-bin/bromade.cgi"
  chmod 755 "$PUBLIC_DIR/cgi-bin/bromade.cgi"
  cp cpanel/htaccess "$PUBLIC_DIR/.htaccess"
  chmod 644 "$PUBLIC_DIR/.htaccess"
  rm -rf "$PUBLIC_DIR/static"
  cp -r staticfiles "$PUBLIC_DIR/static"
  echo "Updated CGI bridge and static files in $PUBLIC_DIR"
fi

touch tmp/restart.txt
echo "Deploy complete."
