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


class SupportTicket(UUIDModel):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        RESOLVED = 'resolved', 'Resolved'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_tickets',
    )
    topic = models.CharField(max_length=80)
    message = models.TextField(max_length=1000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reply = models.TextField(blank=True, help_text='Shown to the customer in the app.')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.topic} · {self.user}'
