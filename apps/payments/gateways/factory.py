from django.conf import settings

from .base import PaymentGateway
from .mock_razorpay import MockRazorpayGateway


def get_payment_gateway() -> PaymentGateway:
    provider = getattr(settings, 'PAYMENT_GATEWAY', 'mock_razorpay')
    if provider == 'mock_razorpay':
        return MockRazorpayGateway()
    raise ValueError(f'Unsupported payment gateway: {provider}')
