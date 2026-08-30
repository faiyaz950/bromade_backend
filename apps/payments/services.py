import uuid

from django.db import transaction

from apps.bookings.models import Booking
from apps.payments.gateways.factory import get_payment_gateway
from apps.payments.models import Payment


class RazorpayGatewayService:
    """Compatibility facade used by payment views."""

    @staticmethod
    def create_order(booking):
        return get_payment_gateway().create_order(booking)

    @staticmethod
    def verify_payment(payment, gateway_payment_id, signature=''):
        return get_payment_gateway().verify_payment(payment, gateway_payment_id, signature)


class CashPaymentService:
    """Cash-on-service flow: the customer pays the partner directly after the visit.

    No money moves through the platform at booking time, so there is no
    gateway callback to wait for — the booking is confirmed and a partner
    assigned immediately. Revenue distribution between partner and platform
    is handled manually by an admin, outside the app.
    """

    @staticmethod
    @transaction.atomic
    def create_order(booking: Booking) -> Payment:
        payment = Payment.objects.create(
            booking=booking,
            gateway='cash',
            gateway_order_id=f'cash_{uuid.uuid4().hex[:16]}',
            method=Payment.Method.CASH,
            amount=booking.total_amount,
            status=Payment.Status.CASH_PENDING,
            payload={'mode': 'cash'},
        )

        booking.start_visit_tracking(
            note='Cash booking confirmed; customer will pay the partner after service.',
        )

        from apps.partners.assignment_service import AssignmentService

        AssignmentService.auto_assign_booking(booking)
        return payment
