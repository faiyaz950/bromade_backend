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
    is_active = models.BooleanField(default=False)
    is_available_for_assignment = models.BooleanField(default=True)
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
