from decimal import Decimal

from django.db import transaction

from apps.catalog.models import CityPackagePrice
from apps.coupons.models import Coupon, CouponRedemption
from apps.coupons.services import CouponService, CouponValidationError

from .models import Booking, BookingItem, BookingStatusLog


class BookingService:
    @staticmethod
    @transaction.atomic
    def create_booking(*, user, package, address, scheduled_date, scheduled_time, notes='', quantity=1, coupon=None):
        city_price = CityPackagePrice.objects.filter(city=address.city, package=package, is_active=True).first()
        unit_price = city_price.discounted_price if city_price else package.discounted_price
        subtotal = Decimal(unit_price) * quantity
        discount = Decimal('0.00')
        applied_coupon = None

        if coupon is not None:
            locked = Coupon.objects.select_for_update().get(pk=coupon.pk)
            try:
                applied_coupon, subtotal, discount, total = CouponService.validate(
                    user=user,
                    code=locked.code,
                    package=package,
                    city=address.city,
                    quantity=quantity,
                    coupon=locked,
                )
            except CouponValidationError as exc:
                raise ValueError(exc.message) from exc
        else:
            total = subtotal

        booking = Booking.objects.create(
            customer=user,
            address=address,
            city=address.city,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            status=Booking.Status.PENDING_PAYMENT,
            subtotal_amount=subtotal,
            discount_amount=discount,
            total_amount=total,
            coupon=applied_coupon,
            coupon_code=applied_coupon.code if applied_coupon else '',
            notes=notes,
        )
        BookingItem.objects.create(
            booking=booking,
            package=package,
            service_name=package.service.name,
            package_name=package.name,
            unit_price=unit_price,
            quantity=quantity,
            line_total=subtotal,
        )
        if applied_coupon is not None:
            CouponRedemption.objects.create(
                coupon=applied_coupon,
                user=user,
                booking=booking,
                discount_amount=discount,
            )
        BookingStatusLog.objects.create(
            booking=booking,
            from_status='',
            to_status=Booking.Status.PENDING_PAYMENT,
            note='Booking draft created and awaiting payment.',
        )
        return booking
