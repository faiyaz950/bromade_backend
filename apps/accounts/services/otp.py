from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import OTPRequest

logger = logging.getLogger(__name__)


class OTPProvider(ABC):
    """Abstract OTP delivery provider so SMS vendors can be swapped later."""

    @abstractmethod
    def send(self, phone_number: str, code: str) -> None:
        raise NotImplementedError


class MockOTPProvider(OTPProvider):
    """Development provider that logs OTP instead of sending SMS."""

    def send(self, phone_number: str, code: str) -> None:
        logger.info('Mock OTP for %s: %s', phone_number, code)


class OTPService:
    def __init__(self, provider: OTPProvider | None = None):
        self.provider = provider or get_otp_provider()

    def request_otp(self, phone_number: str) -> OTPRequest:
        code = f'{random.randint(100000, 999999)}'
        otp_request = OTPRequest.objects.create(
            phone_number=phone_number,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        self.provider.send(phone_number, code)
        return otp_request

    def verify_otp(self, phone_number: str, code: str) -> OTPRequest:
        otp_request = (
            OTPRequest.objects.filter(
                phone_number=phone_number,
                code=code,
                is_used=False,
                expires_at__gte=timezone.now(),
            )
            .order_by('-created_at')
            .first()
        )
        if otp_request is None:
            raise ValueError('Invalid or expired OTP.')
        otp_request.is_used = True
        otp_request.save(update_fields=['is_used', 'updated_at'])
        return otp_request


def get_otp_provider() -> OTPProvider:
    provider_name = getattr(settings, 'OTP_PROVIDER', 'mock')
    if provider_name == 'mock':
        return MockOTPProvider()
    raise ValueError(f'Unsupported OTP provider: {provider_name}')
