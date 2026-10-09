"""Firebase Cloud Messaging (HTTP v1) sender.

Configure with FIREBASE_SERVICE_ACCOUNT_FILE (path to the service account
JSON) or FIREBASE_SERVICE_ACCOUNT_JSON (the JSON itself). Without either,
pushes are logged and skipped so the rest of the app keeps working.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from functools import lru_cache

import requests
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

_SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'
_DEAD_TOKEN_ERRORS = {'UNREGISTERED', 'INVALID_ARGUMENT', 'NOT_FOUND'}


@lru_cache(maxsize=1)
def _credentials():
    from google.oauth2 import service_account

    raw = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_JSON', '') or ''
    path = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_FILE', '') or ''
    if raw:
        info = json.loads(raw)
    elif path:
        with open(path, encoding='utf-8') as handle:
            info = json.load(handle)
    else:
        return None
    return service_account.Credentials.from_service_account_info(info, scopes=[_SCOPE])


def push_enabled() -> bool:
    try:
        return _credentials() is not None
    except Exception:  # noqa: BLE001 - a broken key must never break bookings
        logger.exception('Firebase service account could not be loaded.')
        return False


def _access_token(credentials) -> str:
    from google.auth.transport.requests import Request

    if not credentials.valid:
        credentials.refresh(Request())
    return credentials.token


@dataclass
class DeliveryReport:
    delivered: int = 0
    failed: int = 0
    expired: int = 0


def _send_now(tokens: list[str], title: str, body: str, data: dict[str, str]) -> list[str]:
    return _deliver(tokens, title, body, data)[1]


def deliver_now(tokens, title: str, body: str, data: dict | None = None) -> DeliveryReport:
    """Send inline and report the outcome. Expired tokens are removed."""
    tokens = [token for token in dict.fromkeys(tokens) if token and not token.startswith('local-')]
    payload = {key: str(value) for key, value in (data or {}).items()}
    report, dead = _deliver(tokens, title, body, payload)
    _forget(dead)
    return report


def _deliver(tokens: list[str], title: str, body: str, data: dict[str, str]) -> tuple[DeliveryReport, list[str]]:
    report = DeliveryReport()
    credentials = _credentials()
    if credentials is None or not tokens:
        return report, []
    url = f'https://fcm.googleapis.com/v1/projects/{credentials.project_id}/messages:send'
    dead = []
    with requests.Session() as session:
        for token in tokens:
            message = {
                'message': {
                    'token': token,
                    'notification': {'title': title, 'body': body},
                    'data': data,
                    # channel_id must match the channel the apps create.
                    'android': {
                        'priority': 'high',
                        'notification': {'sound': 'default', 'channel_id': 'booking_updates'},
                    },
                    'apns': {'payload': {'aps': {'sound': 'default'}}},
                }
            }
            # Refreshes itself once the hour-long access token runs out.
            headers = {'Authorization': f'Bearer {_access_token(credentials)}'}
            try:
                reply = session.post(url, json=message, headers=headers, timeout=10)
            except requests.RequestException:
                logger.exception('FCM request failed.')
                report.failed += 1
                continue
            if reply.status_code == 200:
                report.delivered += 1
                continue
            try:
                status = (reply.json().get('error', {}) or {}).get('status', '')
            except ValueError:
                status = ''
            if reply.status_code in (400, 404) and status in _DEAD_TOKEN_ERRORS:
                dead.append(token)
                report.expired += 1
            else:
                report.failed += 1
                logger.warning('FCM rejected a push (%s): %s', reply.status_code, reply.text[:300])
    return report, dead


def _forget(tokens: list[str]) -> None:
    if not tokens:
        return
    from apps.accounts.models import UserDeviceToken
    from apps.partners.models import PartnerDeviceToken

    UserDeviceToken.objects.filter(token__in=tokens).delete()
    PartnerDeviceToken.objects.filter(token__in=tokens).delete()


def send_push(tokens, *, title: str, body: str, data: dict | None = None) -> None:
    """Queue a push for after the current transaction commits."""
    tokens = [token for token in dict.fromkeys(tokens) if token and not token.startswith('local-')]
    if not tokens:
        return
    if not push_enabled():
        logger.info('Push skipped (Firebase not configured): %s', title)
        return
    payload = {key: str(value) for key, value in (data or {}).items()}

    def deliver():
        try:
            _forget(_send_now(tokens, title, body, payload))
        except Exception:  # noqa: BLE001
            logger.exception('Push delivery failed.')

    transaction.on_commit(lambda: threading.Thread(target=deliver, daemon=True).start())
