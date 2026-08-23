from django.db import models

from apps.bookings.models import Booking
from apps.common.models import UUIDModel


class Payment(UUIDModel):
    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        CASH_PENDING = 'cash_pending', 'Cash Pending'

    class Method(models.TextChoices):
        ONLINE = 'online', 'Online'
        CASH = 'cash', 'Cash'

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    gateway = models.CharField(max_length=40, default='razorpay')
    gateway_order_id = models.CharField(max_length=120, unique=True)
    gateway_payment_id = models.CharField(max_length=120, blank=True)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.ONLINE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'gateway'])]

    def __str__(self):
        return self.gateway_order_id
