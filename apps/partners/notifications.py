from __future__ import annotations

import logging

from apps.partners.models import PartnerDeviceToken

logger = logging.getLogger(__name__)


def notify_partner_new_job(partner, booking) -> None:
    tokens = list(PartnerDeviceToken.objects.filter(partner=partner).values_list('token', flat=True))
    logger.info(
        'New job %s assigned to %s (%s token(s)).',
        booking.id,
        partner.full_name,
        len(tokens),
    )
