from __future__ import annotations

import uuid

from apps.bookings.models import Booking
from apps.payments.models import Payment

from .base import PaymentGateway


class MockRazorpayGateway(PaymentGateway):
    """Sandbox/mock Razorpay implementation for local Booking MVP."""

    def create_order(self, booking: Booking) -> Payment:
        gateway_order_id = f'order_{uuid.uuid4().hex[:16]}'
        return Payment.objects.create(
            booking=booking,
            gateway='razorpay',
            gateway_order_id=gateway_order_id,
            amount=booking.total_amount,
            payload={'mode': 'mock', 'provider': 'razorpay'},
        )

    def verify_payment(self, payment: Payment, gateway_payment_id: str, signature: str = '') -> Payment:
        payment.gateway_payment_id = gateway_payment_id
        payment.status = Payment.Status.PAID
        payment.payload = {**payment.payload, 'signature': signature, 'verified': True}
        payment.save(update_fields=['gateway_payment_id', 'status', 'payload', 'updated_at'])

        booking = payment.booking
        booking.start_visit_tracking(note='Payment verified successfully.')

        from apps.partners.assignment_service import AssignmentService

        AssignmentService.auto_assign_booking(booking)
        return payment
