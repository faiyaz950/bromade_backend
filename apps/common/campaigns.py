"""Admin-written push notifications: who gets them and delivery."""
from __future__ import annotations

import logging
import re
import threading
from datetime import timedelta

from django.db import close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone

from .models import PushCampaign
from .push import deliver_now, push_enabled

logger = logging.getLogger(__name__)

# A send that crashed mid-way (e.g. a restart) is reported instead of hanging forever.
_STALE_AFTER = timedelta(minutes=30)


def _matching_users(value: str):
    from apps.accounts.models import User

    value = value.strip()
    if '@' in value:
        return User.objects.filter(email__iexact=value)
    digits = re.sub(r'\D', '', value)
    if len(digits) < 10:
        return User.objects.none()
    return User.objects.filter(phone_number__in={f'+{digits}', f'+91{digits[-10:]}'})


def _customer_tokens():
    from apps.accounts.models import UserDeviceToken

    return UserDeviceToken.objects.filter(user__is_active=True)


def _partner_tokens():
    from apps.partners.models import PartnerDeviceToken, PartnerProfile

    return PartnerDeviceToken.objects.filter(partner__user__is_active=True).exclude(
        partner__approval_status=PartnerProfile.ApprovalStatus.REJECTED
    )


def find_recipient_tokens(audience: str, value: str) -> list[str]:
    users = _matching_users(value)
    if audience == PushCampaign.Audience.PARTNERS:
        tokens = _partner_tokens().filter(partner__user__in=users)
    else:
        tokens = _customer_tokens().filter(user__in=users)
    return list(tokens.values_list('token', flat=True))


def campaign_tokens(campaign: PushCampaign) -> list[str]:
    if campaign.target == PushCampaign.Target.PERSON:
        return find_recipient_tokens(campaign.audience, campaign.recipient)
    partners = campaign.audience == PushCampaign.Audience.PARTNERS
    tokens = _partner_tokens() if partners else _customer_tokens()
    if campaign.target == PushCampaign.Target.CITY:
        if partners:
            tokens = tokens.filter(partner__cities__city=campaign.city_id)
        else:
            tokens = tokens.filter(
                Q(user__addresses__city=campaign.city_id) | Q(user__bookings__city=campaign.city_id)
            )
    return list(dict.fromkeys(tokens.values_list('token', flat=True)))


def campaign_data(campaign: PushCampaign) -> dict[str, str]:
    """What the app reads to decide which screen a tap opens."""
    data = {'type': 'campaign', 'campaign_id': str(campaign.id), 'screen': campaign.screen}
    if campaign.service_id:
        data['service_id'] = str(campaign.service_id)
    if campaign.package_id:
        data['package_id'] = str(campaign.package_id)
        data['service_id'] = str(campaign.package.service_id)
    return data


def deliver_campaign(campaign_id) -> bool:
    """Send one due campaign. Safe to call twice: only one caller claims it."""
    now = timezone.now()
    claimed = PushCampaign.objects.filter(
        pk=campaign_id, status=PushCampaign.Status.SCHEDULED, send_at__lte=now
    ).update(status=PushCampaign.Status.SENDING, updated_at=now)
    if not claimed:
        return False
    campaign = PushCampaign.objects.select_related('package').get(pk=campaign_id)
    result = {'sent_at': timezone.now(), 'updated_at': timezone.now()}
    try:
        if not push_enabled():
            raise RuntimeError('Push is not configured on the server (Firebase key missing).')
        tokens = campaign_tokens(campaign)
        report = deliver_now(tokens, campaign.title, campaign.body, campaign_data(campaign))
        result.update(
            status=PushCampaign.Status.SENT,
            devices=len(tokens),
            delivered=report.delivered,
            failed=report.failed + report.expired,
        )
    except Exception as error:  # noqa: BLE001 - recorded on the campaign for the team to see
        logger.exception('Push campaign %s failed.', campaign_id)
        result.update(status=PushCampaign.Status.FAILED, error=str(error)[:255])
    PushCampaign.objects.filter(pk=campaign_id).update(**result)
    return True


def send_in_background(campaign_id) -> None:
    """Deliver after the admin save commits, without holding up the page."""

    def run():
        try:
            deliver_campaign(campaign_id)
        finally:
            close_old_connections()

    transaction.on_commit(lambda: threading.Thread(target=run, daemon=True).start())


def send_due_campaigns() -> int:
    now = timezone.now()
    PushCampaign.objects.filter(
        status=PushCampaign.Status.SENDING, updated_at__lt=now - _STALE_AFTER
    ).update(
        status=PushCampaign.Status.FAILED,
        error='Stopped part-way (server restarted). Some phones may have received it.',
        updated_at=now,
    )
    due = PushCampaign.objects.filter(status=PushCampaign.Status.SCHEDULED, send_at__lte=now)
    return sum(deliver_campaign(pk) for pk in due.order_by('send_at').values_list('pk', flat=True))
