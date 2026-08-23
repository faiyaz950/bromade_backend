from django.conf import settings
from django.db import models

from apps.common.models import UUIDModel


class CustomerProfile(UUIDModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_profile')
    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        ordering = ['full_name', 'created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return self.full_name or self.user.phone_number
