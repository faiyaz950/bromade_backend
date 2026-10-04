from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify_partner_new_job(partner, booking) -> None:
    from apps.bookings.notifications import _service_name, notify_partner

    logger.info('New job %s offered to %s.', booking.id, partner.full_name)
    notify_partner(
        partner,
        booking,
        'New job request',
        f'{_service_name(booking)} on {booking.scheduled_date:%d %b} at '
        f'{booking.scheduled_time:%I:%M %p} · ₹{booking.total_amount:.0f}. Open to accept.',
    )
