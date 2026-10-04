from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import CityPackagePrice
from apps.coupons.models import Coupon, CouponRedemption
from apps.coupons.services import CouponService, CouponValidationError

from .models import Booking, BookingAssignment, BookingItem, BookingStatusLog

MAX_RESCHEDULES = 2
MIN_LEAD_TIME = timedelta(hours=1)
CANCEL_WINDOW = timedelta(minutes=60)
CHANGEABLE_STATUSES = {Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED}
CHANGEABLE_VISIT_STATUSES = {'', Booking.VisitStatus.NONE, Booking.VisitStatus.SCHEDULED}


def can_change(booking) -> bool:
    """Customers can change a booking until the professional sets off."""
    return booking.status in CHANGEABLE_STATUSES and booking.visit_status in CHANGEABLE_VISIT_STATUSES


def cancel_deadline(booking):
    return booking.created_at + CANCEL_WINDOW


def can_cancel(booking) -> bool:
    return can_change(booking) and timezone.now() <= cancel_deadline(booking)


def can_reschedule(booking) -> bool:
    return can_change(booking) and booking.reschedule_count < MAX_RESCHEDULES


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

    @staticmethod
    @transaction.atomic
    def cancel_booking(*, booking, reason=''):
        from apps.partners.wallet_service import WalletService, commission_amount
        from apps.payments.models import Payment

        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        if not can_change(booking):
            raise ValueError('This booking can no longer be cancelled. The professional is already on the way.')
        if timezone.now() > cancel_deadline(booking):
            raise ValueError(
                'Bookings can only be cancelled within 60 minutes of booking. Please chat with support for help.'
            )

        from .notifications import active_partners, partners_booking_cancelled

        now = timezone.now()
        partners_to_notify = active_partners(booking)
        accepted = (
            BookingAssignment.objects.select_related('partner')
            .filter(booking=booking, status=BookingAssignment.Status.ACCEPTED)
            .first()
        )
        if accepted is not None:
            WalletService.credit(
                partner=accepted.partner,
                amount=commission_amount(booking.total_amount),
                note='Commission refund: customer cancelled the job',
                booking=booking,
            )
        BookingAssignment.objects.filter(
            booking=booking,
            status__in=[BookingAssignment.Status.PENDING, BookingAssignment.Status.ACCEPTED],
        ).update(
            status=BookingAssignment.Status.REASSIGNED,
            rejection_reason='Customer cancelled the booking.',
            responded_at=now,
            updated_at=now,
        )
        booking.payments.filter(
            status__in=[Payment.Status.CREATED, Payment.Status.CASH_PENDING],
        ).update(status=Payment.Status.FAILED, updated_at=now)

        previous = booking.status
        booking.status = Booking.Status.CANCELLED
        booking.cancellation_reason = (reason or '').strip()[:255]
        booking.cancelled_at = now
        booking.save(update_fields=['status', 'cancellation_reason', 'cancelled_at', 'updated_at'])
        BookingStatusLog.objects.create(
            booking=booking,
            from_status=previous,
            to_status=Booking.Status.CANCELLED,
            note=f'Cancelled by customer. {booking.cancellation_reason}'.strip()[:255],
        )
        partners_booking_cancelled(
            booking,
            partners_to_notify,
            refunded_partner=accepted.partner if accepted else None,
        )
        return booking

    @staticmethod
    @transaction.atomic
    def reschedule_booking(*, booking, scheduled_date, scheduled_time):
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        if not can_change(booking):
            raise ValueError('This booking can no longer be rescheduled. The professional is already on the way.')
        if booking.reschedule_count >= MAX_RESCHEDULES:
            raise ValueError(f'A booking can be rescheduled only {MAX_RESCHEDULES} times.')
        slot = timezone.make_aware(datetime.combine(scheduled_date, scheduled_time))
        if slot < timezone.now() + MIN_LEAD_TIME:
            raise ValueError('Pick a slot at least 1 hour from now.')
        if scheduled_date == booking.scheduled_date and scheduled_time == booking.scheduled_time:
            raise ValueError('Pick a different date or time.')

        old = f'{booking.scheduled_date:%d %b} {booking.scheduled_time:%H:%M}'
        booking.scheduled_date = scheduled_date
        booking.scheduled_time = scheduled_time
        booking.reschedule_count += 1
        booking.save(update_fields=['scheduled_date', 'scheduled_time', 'reschedule_count', 'updated_at'])
        BookingStatusLog.objects.create(
            booking=booking,
            from_status=booking.status,
            to_status='rescheduled',
            note=f'Customer moved the visit from {old} to {scheduled_date:%d %b} {scheduled_time:%H:%M}.',
        )
        from .notifications import partners_booking_rescheduled

        partners_booking_rescheduled(booking)
        return booking
