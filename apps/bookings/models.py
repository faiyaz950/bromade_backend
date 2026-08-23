from django.conf import settings
from django.db import models

from apps.catalog.models import ServicePackage
from apps.common.models import UUIDModel
from apps.locations.models import Address, City


class Booking(UUIDModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING_PAYMENT = 'pending_payment', 'Pending Payment'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'

    class AssignmentStatus(models.TextChoices):
        UNASSIGNED = 'unassigned', 'Unassigned'
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    address = models.ForeignKey(Address, on_delete=models.PROTECT, related_name='bookings')
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name='bookings')
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    assignment_status = models.CharField(
        max_length=30,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.UNASSIGNED,
    )
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['scheduled_date', 'scheduled_time']),
        ]

    def __str__(self):
        return f'Booking {self.pk} - {self.customer.phone_number}'


class BookingItem(UUIDModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='items')
    package = models.ForeignKey(ServicePackage, on_delete=models.PROTECT, related_name='booking_items')
    service_name = models.CharField(max_length=150)
    package_name = models.CharField(max_length=150)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.package_name} x {self.quantity}'


class BookingStatusLog(UUIDModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='status_logs')
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.booking_id}: {self.from_status} -> {self.to_status}'


class BookingAssignment(UUIDModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'
        REASSIGNED = 'reassigned', 'Reassigned'

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='assignments')
    partner = models.ForeignKey('partners.PartnerProfile', on_delete=models.CASCADE, related_name='assignments')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.CharField(max_length=255, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-assigned_at']
        verbose_name = 'Partner job'
        verbose_name_plural = 'Partner jobs'
        indexes = [
            models.Index(fields=['partner', 'status']),
            models.Index(fields=['booking', 'status']),
        ]

    def __str__(self):
        return f'{self.booking_id} -> {self.partner_id} ({self.status})'
