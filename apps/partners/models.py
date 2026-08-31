from django.conf import settings
from django.db import models

from apps.catalog.models import Service
from apps.common.models import UUIDModel
from apps.locations.models import City


class PartnerProfile(UUIDModel):
    class ApprovalStatus(models.TextChoices):
        PENDING = 'pending', 'Pending approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='partner_profile',
    )
    full_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    pincode = models.CharField(max_length=6, blank=True)
    years_experience = models.PositiveSmallIntegerField(default=0)
    aadhaar_number = models.CharField(max_length=12, blank=True)
    pan_number = models.CharField(max_length=10, blank=True)
    upi_id = models.CharField(max_length=100, blank=True)
    upi_phone = models.CharField(max_length=10, blank=True)
    bank_account_holder = models.CharField(max_length=150, blank=True)
    bank_account_number = models.CharField(max_length=20, blank=True)
    bank_ifsc = models.CharField(max_length=11, blank=True)
    is_active = models.BooleanField(default=False)
    is_available_for_assignment = models.BooleanField(default=True)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    approval_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['full_name']
        verbose_name = 'Partner'
        verbose_name_plural = 'Partners'

    def __str__(self):
        return self.full_name or self.user.phone_number

    @property
    def registration_is_complete(self):
        if not (self.full_name or '').strip():
            return False
        if not (self.address_line or '').strip():
            return False
        if len(''.join(ch for ch in (self.pincode or '') if ch.isdigit())) != 6:
            return False
        if len(''.join(ch for ch in (self.aadhaar_number or '') if ch.isdigit())) != 12:
            return False
        if not self.cities.exists() or not self.services.exists():
            return False
        return True


class PartnerCity(UUIDModel):
    partner = models.ForeignKey(PartnerProfile, on_delete=models.CASCADE, related_name='cities')
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='partner_cities')

    class Meta:
        unique_together = ('partner', 'city')
        ordering = ['city__name']

    def __str__(self):
        return f'{self.partner.full_name} · {self.city.name}'


class PartnerService(UUIDModel):
    partner = models.ForeignKey(PartnerProfile, on_delete=models.CASCADE, related_name='services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='partner_services')

    class Meta:
        unique_together = ('partner', 'service')
        ordering = ['service__name']

    def __str__(self):
        return f'{self.partner.full_name} · {self.service.name}'


class PartnerDeviceToken(UUIDModel):
    partner = models.ForeignKey(PartnerProfile, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255)
    platform = models.CharField(max_length=20, default='android')

    class Meta:
        unique_together = ('partner', 'token')
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.partner.full_name} · {self.platform}'


class PartnerUnavailableDate(UUIDModel):
    partner = models.ForeignKey(PartnerProfile, on_delete=models.CASCADE, related_name='unavailable_dates')
    date = models.DateField()
    note = models.CharField(max_length=120, blank=True)

    class Meta:
        unique_together = ('partner', 'date')
        ordering = ['date']

    def __str__(self):
        return f'{self.partner.full_name} · {self.date}'


class WalletTransaction(UUIDModel):
    class EntryType(models.TextChoices):
        CREDIT = 'credit', 'Credit'
        DEBIT = 'debit', 'Debit'

    partner = models.ForeignKey(PartnerProfile, on_delete=models.CASCADE, related_name='wallet_transactions')
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='partner_wallet_credits',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.partner} · {self.entry_type} · {self.amount}'
