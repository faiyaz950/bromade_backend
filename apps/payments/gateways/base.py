from __future__ import annotations

from abc import ABC, abstractmethod

from apps.bookings.models import Booking
from apps.payments.models import Payment


class PaymentGateway(ABC):
    """Payment gateway abstraction for Razorpay and future providers."""

    @abstractmethod
    def create_order(self, booking: Booking) -> Payment:
        raise NotImplementedError

    @abstractmethod
    def verify_payment(self, payment: Payment, gateway_payment_id: str, signature: str = '') -> Payment:
        raise NotImplementedError
