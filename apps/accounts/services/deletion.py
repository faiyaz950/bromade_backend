from django.db import transaction
from django.db.models import Q

from apps.accounts.models import UserDeviceToken
from apps.bookings.models import Booking
from apps.coupons.models import ReferralCode
from apps.customers.models import CustomerProfile
from apps.locations.models import Address

UPCOMING_STATUSES = (Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED)


class AccountDeletionBlocked(Exception):
    pass


def delete_customer_account(user):
    """Erase a customer's personal data and close the account.

    Bookings (and the payments and partner earnings that hang off them) are
    kept for accounting, but stripped of anything that identifies the person.
    """
    if hasattr(user, 'partner_profile'):
        raise AccountDeletionBlocked(
            'This account is also a Demess partner account. Contact support to close it.'
        )
    if user.bookings.filter(status__in=UPCOMING_STATUSES).exists():
        raise AccountDeletionBlocked(
            'You have an upcoming booking. Cancel it or wait until the visit is done, then delete your account.'
        )

    with transaction.atomic():
        UserDeviceToken.objects.filter(user=user).delete()
        CustomerProfile.objects.filter(user=user).delete()
        ReferralCode.objects.filter(user=user).delete()
        user.support_tickets.all().delete()

        with_photos = user.bookings.filter(Q(start_photo__gt='') | Q(completion_photo__gt=''))
        photo_files = []
        for booking in with_photos:
            for photo in (booking.start_photo, booking.completion_photo):
                if photo:
                    photo_files.append((photo.storage, photo.name))
            booking.start_photo = None
            booking.completion_photo = None
            booking.save(update_fields=['start_photo', 'completion_photo', 'updated_at'])
        user.bookings.update(notes='')
        transaction.on_commit(lambda: [storage.delete(name) for storage, name in photo_files])

        # Booking.address is PROTECT, so addresses on past bookings are wiped
        # in place; the rest are deleted.
        booked = Address.objects.filter(user=user, bookings__isnull=False).distinct()
        Address.objects.filter(user=user).exclude(pk__in=booked).delete()
        Address.objects.filter(pk__in=booked).update(
            label='Deleted',
            contact_name='Deleted user',
            contact_phone='',
            line1='Removed on account deletion',
            line2='',
            landmark='',
            latitude=None,
            longitude=None,
            is_default=False,
        )

        user.phone_number = None
        user.email = None
        user.google_id = None
        user.first_name = ''
        user.last_name = ''
        user.is_active = False
        user.set_unusable_password()
        user.save()
