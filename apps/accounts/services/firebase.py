from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


def verify_id_token(token: str) -> dict:
    project_id = getattr(settings, 'FIREBASE_PROJECT_ID', '') or ''
    if not project_id:
        raise ValueError('Firebase is not configured.')
    decoded = id_token.verify_firebase_token(
        token,
        google_requests.Request(),
        audience=project_id,
    )
    if not decoded:
        raise ValueError('Invalid Firebase token.')
    return decoded
