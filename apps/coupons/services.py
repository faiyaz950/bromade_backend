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
        return ''.join(ch for ch in (code or '').upper() if ch.isalnum())

    @staticmethod
    def compact_code(code):
        return CouponService.normalize_code(code)

    @staticmethod
    def find_coupon(code):
        compact = CouponService.compact_code(code)
        if not compact:
            return None
        qs = Coupon.objects.prefetch_related('services', 'packages', 'cities')
        coupon = qs.filter(code=compact).first()
        if coupon is not None:
            return coupon
        coupon = qs.filter(code__iexact=compact).first()
        if coupon is not None:
            return coupon
        for candidate in qs.iterator():
            if CouponService.compact_code(candidate.code) == compact:
                return candidate
        return None

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
    def discount_label(coupon):
        if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
            label = f'{Decimal(coupon.discount_value):.0f}% off'
            if coupon.max_discount_amount is not None:
                label += f' up to ₹{Decimal(coupon.max_discount_amount):.0f}'
            return label
        return f'₹{Decimal(coupon.discount_value):.0f} off'

    @staticmethod
    def list_offers(*, user, package, city=None, quantity=1):
        today = timezone.localdate()
        qs = (
            Coupon.objects.filter(is_active=True)
            .prefetch_related('services', 'packages', 'cities')
            .order_by('code')
        )
        offers = []
        for coupon in qs:
            if coupon.valid_from and today < coupon.valid_from:
                continue
            if coupon.valid_until and today > coupon.valid_until:
                continue
            eligible = True
            try:
                CouponService.validate(
                    code=coupon.code,
                    package=package,
                    user=user,
                    city=city,
                    quantity=quantity,
                    coupon=coupon,
                )
            except CouponValidationError:
                eligible = False
            offers.append({
                'code': coupon.code,
                'title': coupon.title,
                'discount_label': CouponService.discount_label(coupon),
                'eligible': eligible,
            })
        offers.sort(key=lambda item: (not item['eligible'], item['code']))
        return offers

    @staticmethod
    def validate(*, code, package, user=None, city=None, quantity=1, coupon=None):
        """Return (coupon, subtotal, discount, total) or raise CouponValidationError."""
        if coupon is None:
            if not CouponService.normalize_code(code):
                raise CouponValidationError('Enter a coupon code.')
            coupon = CouponService.find_coupon(code)
            if coupon is None:
                raise CouponValidationError(
                    'This coupon code was not found. Check the spelling matches the admin code.'
                )

        if not coupon.is_active:
            raise CouponValidationError('This coupon is turned off.')

        today = timezone.localdate()
        if coupon.valid_from and today < coupon.valid_from:
            raise CouponValidationError('This coupon is not active yet.')
        if coupon.valid_until and today > coupon.valid_until:
            raise CouponValidationError('This coupon has expired.')

        apply_scope = getattr(coupon, 'apply_scope', Coupon.ApplyScope.ALL_SERVICES)
        if apply_scope == Coupon.ApplyScope.SELECTED_SERVICES:
            allowed_services = {str(service_id) for service_id in coupon.services.values_list('pk', flat=True)}
            if not allowed_services:
                raise CouponValidationError('This coupon has no services selected in admin.')
            if str(package.service_id) not in allowed_services:
                names = ', '.join(coupon.services.values_list('name', flat=True)[:4]) or 'selected services'
                raise CouponValidationError(
                    f'This coupon is only for {names}, not for {package.service.name}.'
                )
            if coupon.packages.exists() and not coupon.packages.filter(pk=package.pk).exists():
                raise CouponValidationError('This coupon isn’t valid on this package.')

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
