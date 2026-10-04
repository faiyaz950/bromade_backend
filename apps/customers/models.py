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
    """A support conversation between a customer and the Bayti team."""

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
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    customer_read_at = models.DateTimeField(null=True, blank=True)
    admin_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_message_at', '-created_at']
        verbose_name = 'Support chat'
        verbose_name_plural = 'Support chats'

    def __str__(self):
        return f'{self.topic} · {self.user}'

    def unread_for_customer(self):
        qs = self.messages.filter(sender=SupportMessage.Sender.SUPPORT)
        if self.customer_read_at:
            qs = qs.filter(created_at__gt=self.customer_read_at)
        return qs.count()

    def unread_for_admin(self):
        qs = self.messages.filter(sender=SupportMessage.Sender.CUSTOMER)
        if self.admin_read_at:
            qs = qs.filter(created_at__gt=self.admin_read_at)
        return qs.count()


class SupportMessage(UUIDModel):
    class Sender(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        SUPPORT = 'support', 'Support'

    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=20, choices=Sender.choices)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    body = models.TextField(max_length=2000)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender}: {self.body[:40]}'
