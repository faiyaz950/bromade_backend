from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.common.models import UUIDModel


class Coupon(UUIDModel):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage (%)'
        FIXED = 'fixed', 'Fixed amount (₹)'

    class ApplyScope(models.TextChoices):
        ALL_SERVICES = 'all_services', 'All services'
        SELECTED_SERVICES = 'selected_services', 'Selected services only'

    code = models.CharField(
        max_length=40,
        unique=True,
        help_text='Customers type this in the app. Saved in uppercase, e.g. WELCOME50.',
    )
    title = models.CharField(
        max_length=120,
        help_text='Short label shown in admin and in the app after apply, e.g. Welcome offer.',
    )
    description = models.TextField(blank=True, help_text='Optional internal notes. Not shown in the app.')
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='For percentage: 10 means 10% off. For fixed: 100 means ₹100 off.',
    )
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Minimum package price (after catalog discount) required to use this coupon. 0 = no minimum.',
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Optional cap for percentage coupons, e.g. 20% off up to ₹200. Leave blank for no cap.',
    )
    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Total times this coupon can be used across all customers. Leave blank for unlimited.',
    )
    usage_limit_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=1,
        help_text='How many times one customer can use this coupon. Leave blank for unlimited. Default is 1.',
    )
    valid_from = models.DateField(null=True, blank=True, help_text='Leave blank to start immediately.')
    valid_until = models.DateField(null=True, blank=True, help_text='Leave blank for no expiry.')
    is_active = models.BooleanField(default=True, help_text='Turn off to hide this coupon from the app without deleting it.')
    apply_scope = models.CharField(
        max_length=30,
        choices=ApplyScope.choices,
        default=ApplyScope.ALL_SERVICES,
        help_text='All services = one code for every service. Selected services = this code only works on the services you pick below.',
    )
    cities = models.ManyToManyField(
        'locations.City',
        blank=True,
        related_name='coupons',
        help_text='Leave empty to allow all cities.',
    )
    services = models.ManyToManyField(
        'catalog.Service',
        blank=True,
        related_name='coupons',
        help_text='Used only when “Selected services only” is chosen. Hold Ctrl/Cmd to pick more than one.',
    )
    packages = models.ManyToManyField(
        'catalog.ServicePackage',
        blank=True,
        related_name='coupons',
        help_text='Leave empty to allow all packages.',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = (self.code or '').strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.discount_value is None:
            return
        if self.discount_value <= 0:
            raise ValidationError({'discount_value': 'Discount value must be greater than 0.'})
        if self.discount_type == self.DiscountType.PERCENTAGE and self.discount_value > 100:
            raise ValidationError({'discount_value': 'Percentage cannot be more than 100.'})
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            raise ValidationError({'valid_until': 'End date must be on or after the start date.'})

    def active_redemptions(self):
        return self.redemptions.exclude(booking__status='cancelled')

    def times_used(self):
        return self.active_redemptions().count()

    def times_used_by(self, user):
        if user is None or not getattr(user, 'is_authenticated', False):
            return 0
        return self.active_redemptions().filter(user=user).count()

    def is_currently_valid(self):
        if not self.is_active:
            return False
        today = timezone.localdate()
        if self.valid_from and today < self.valid_from:
            return False
        if self.valid_until and today > self.valid_until:
            return False
        return True


class CouponRedemption(UUIDModel):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name='redemptions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coupon_redemptions')
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='coupon_redemption',
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['coupon', 'booking'], name='unique_coupon_booking_redemption'),
        ]
        indexes = [
            models.Index(fields=['coupon', 'user']),
        ]

    def __str__(self):
        return f'{self.coupon.code} on booking {self.booking_id}'
