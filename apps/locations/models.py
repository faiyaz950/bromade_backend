from django.conf import settings
from django.db import models

from apps.common.models import UUIDModel


class City(UUIDModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    state = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Cities'

    def __str__(self):
        return self.name


class Address(UUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name='addresses')
    label = models.CharField(max_length=80)
    contact_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=20)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    pincode = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        verbose_name_plural = 'Addresses'
        indexes = [
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['city']),
        ]

    def __str__(self):
        return f'{self.label} - {self.user.phone_number}'
