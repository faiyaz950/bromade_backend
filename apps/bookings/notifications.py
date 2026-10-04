from __future__ import annotations

from apps.common.push import send_push

from .models import Booking, BookingAssignment


def _service_name(booking: Booking) -> str:
    item = booking.items.first()
    return item.package_name if item else 'your service'


def _first_name(partner) -> str:
    name = (partner.full_name or '').strip()
    return name.split()[0] if name else 'Your professional'


def _customer_tokens(booking: Booking):
    from apps.accounts.models import UserDeviceToken

    return UserDeviceToken.objects.filter(user_id=booking.customer_id).values_list('token', flat=True)


def _partner_tokens(partner):
    return partner.device_tokens.values_list('token', flat=True)


def notify_customer(booking: Booking, title: str, body: str) -> None:
    send_push(
        _customer_tokens(booking),
        title=title,
        body=body,
        data={'type': 'booking', 'booking_id': str(booking.id)},
    )


def notify_partner(partner, booking: Booking, title: str, body: str) -> None:
    send_push(
        _partner_tokens(partner),
        title=title,
        body=body,
        data={'type': 'job', 'booking_id': str(booking.id)},
    )


def customer_partner_assigned(booking: Booking, partner) -> None:
    notify_customer(
        booking,
        'Professional assigned',
        f'{_first_name(partner)} will handle {_service_name(booking)} on '
        f'{booking.scheduled_date:%d %b} at {booking.scheduled_time:%I:%M %p}.',
    )


VISIT_MESSAGES = {
    Booking.VisitStatus.ON_THE_WAY: ('{who} is on the way', 'Please be available at your address.'),
    Booking.VisitStatus.ARRIVED: (
        '{who} has arrived',
        'Share your start code with {who} so the service can begin.',
    ),
    Booking.VisitStatus.IN_PROGRESS: ('Service started', '{who} has started {service}.'),
    Booking.VisitStatus.COMPLETED: ('Service completed', 'How did {who} do? Tap to rate your visit.'),
}


def customer_visit_update(booking: Booking, partner, visit_status: str) -> None:
    template = VISIT_MESSAGES.get(visit_status)
    if template is None:
        return
    values = {'who': _first_name(partner), 'service': _service_name(booking)}
    notify_customer(booking, template[0].format(**values), template[1].format(**values))


def customer_cash_received(booking: Booking, partner) -> None:
    notify_customer(
        booking,
        'Payment received',
        f'{_first_name(partner)} confirmed your ₹{booking.total_amount:.0f} cash payment.',
    )


def active_partners(booking: Booking):
    return [
        assignment.partner
        for assignment in booking.assignments.select_related('partner').filter(
            status__in=[BookingAssignment.Status.PENDING, BookingAssignment.Status.ACCEPTED]
        )
    ]


def partners_booking_cancelled(booking: Booking, partners, refunded_partner=None) -> None:
    for partner in partners:
        refund = ' Your commission is back in your wallet.' if partner == refunded_partner else ''
        notify_partner(
            partner,
            booking,
            'Job cancelled',
            f'The customer cancelled {_service_name(booking)} on {booking.scheduled_date:%d %b}.{refund}',
        )


def partners_booking_rescheduled(booking: Booking) -> None:
    for partner in active_partners(booking):
        notify_partner(
            partner,
            booking,
            'Job rescheduled',
            f'{_service_name(booking)} moved to {booking.scheduled_date:%d %b} at '
            f'{booking.scheduled_time:%I:%M %p}.',
        )
