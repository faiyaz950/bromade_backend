from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from apps.catalog.models import CityPackagePrice

from .models import Coupon


class CouponValidationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


TWOPLACES = Decimal('0.01')


class CouponService:
    @staticmethod
    def normalize_code(code):
        return (code or '').strip().upper()

    @staticmethod
    def resolve_subtotal(*, package, city=None, quantity=1):
        city_price = None
        if city is not None:
            city_price = CityPackagePrice.objects.filter(city=city, package=package, is_active=True).first()
        unit_price = city_price.discounted_price if city_price else package.discounted_price
        return (Decimal(unit_price) * quantity).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def calculate_discount(coupon, subtotal):
        subtotal = Decimal(subtotal)
        if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
            amount = (subtotal * Decimal(coupon.discount_value) / Decimal('100')).quantize(
                TWOPLACES, rounding=ROUND_HALF_UP
            )
            if coupon.max_discount_amount is not None:
                amount = min(amount, Decimal(coupon.max_discount_amount))
        else:
            amount = Decimal(coupon.discount_value)
        if amount > subtotal:
            amount = subtotal
        return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def validate(*, code, package, user=None, city=None, quantity=1, coupon=None):
        """Return (coupon, subtotal, discount, total) or raise CouponValidationError."""
        if coupon is None:
            normalized = CouponService.normalize_code(code)
            if not normalized:
                raise CouponValidationError('Enter a coupon code.')
            coupon = Coupon.objects.filter(code=normalized).first()
            if coupon is None:
                raise CouponValidationError('This coupon isn’t valid on this booking.')

        if not coupon.is_active:
            raise CouponValidationError('This coupon isn’t valid on this booking.')

        today = timezone.localdate()
        if coupon.valid_from and today < coupon.valid_from:
            raise CouponValidationError('This coupon is not active yet.')
        if coupon.valid_until and today > coupon.valid_until:
            raise CouponValidationError('This coupon has expired.')

        if coupon.packages.exists() and not coupon.packages.filter(pk=package.pk).exists():
            raise CouponValidationError('This coupon isn’t valid on this booking.')
        elif coupon.apply_scope == Coupon.ApplyScope.SELECTED_SERVICES:
            if not coupon.services.filter(pk=package.service_id).exists():
                raise CouponValidationError('This coupon isn’t valid on this service.')

        if coupon.cities.exists():
            if city is None:
                raise CouponValidationError('Select an address before applying this coupon.')
            if not coupon.cities.filter(pk=city.pk).exists():
                raise CouponValidationError('This coupon isn’t available in your city.')

        subtotal = CouponService.resolve_subtotal(package=package, city=city, quantity=quantity)
        if Decimal(coupon.min_order_amount) > 0 and subtotal < Decimal(coupon.min_order_amount):
            raise CouponValidationError(
                f'This coupon needs a minimum order of ₹{Decimal(coupon.min_order_amount):.0f}.'
            )

        if coupon.usage_limit is not None and coupon.times_used() >= coupon.usage_limit:
            raise CouponValidationError('This coupon has reached its usage limit.')

        if user is not None and getattr(user, 'is_authenticated', False) and coupon.usage_limit_per_user is not None:
            if coupon.times_used_by(user) >= coupon.usage_limit_per_user:
                raise CouponValidationError('You have already used this coupon.')

        discount = CouponService.calculate_discount(coupon, subtotal)
        if discount <= 0:
            raise CouponValidationError('This coupon isn’t valid on this booking.')

        total = (subtotal - discount).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        return coupon, subtotal, discount, total
