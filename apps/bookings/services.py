from decimal import Decimal

from apps.catalog.models import CityPackagePrice

from .models import Booking, BookingItem, BookingStatusLog


class BookingService:
    @staticmethod
    def create_booking(*, user, package, address, scheduled_date, scheduled_time, notes='', quantity=1):
        city_price = CityPackagePrice.objects.filter(city=address.city, package=package, is_active=True).first()
        unit_price = city_price.discounted_price if city_price else package.discounted_price
        subtotal = Decimal(unit_price) * quantity
        booking = Booking.objects.create(
            customer=user,
            address=address,
            city=address.city,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            status=Booking.Status.PENDING_PAYMENT,
            subtotal_amount=subtotal,
            total_amount=subtotal,
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
        BookingStatusLog.objects.create(
            booking=booking,
            from_status='',
            to_status=Booking.Status.PENDING_PAYMENT,
            note='Booking draft created and awaiting payment.',
        )
        return booking
