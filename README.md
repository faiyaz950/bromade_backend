# Brolytics Backend

Booking MVP backend for Brolytics Home Services.

## Setup

1. Create a virtual environment and install dependencies.
2. Copy `.env.example` to `.env`.
3. Run migrations.
4. Create a superuser.
5. Seed catalog data.

## Commands

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_booking_mvp
python manage.py runserver
```

API base path: `/api/v1/`
Swagger docs: `/api/docs/`

## Render

This repo includes a root `render.yaml`. After connecting the GitHub repo, deploy with **Dashboard → Blueprints → New Blueprint Instance**.

```bash
./build.sh
python -m gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --timeout 60
```
