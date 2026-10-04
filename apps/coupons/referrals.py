import secrets
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Booking

from .models import Coupon, Referral, ReferralCode
from .services import CouponValidationError

REFERRAL_REWARD = Decimal('100')
REFERRAL_MIN_ORDER = Decimal('299')
_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def _random(length):
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))


def _unique_coupon_code(prefix):
    while True:
        code = f'{prefix}{_random(6)}'
        if not Coupon.objects.filter(code=code).exists():
            return code


def _reward_coupon(*, owner, prefix, title):
    return Coupon.objects.create(
        owner=owner,
        code=_unique_coupon_code(prefix),
        title=title,
        description='Created automatically by the referral programme.',
        discount_type=Coupon.DiscountType.FIXED,
        discount_value=REFERRAL_REWARD,
        min_order_amount=REFERRAL_MIN_ORDER,
        usage_limit=1,
        usage_limit_per_user=1,
        is_active=True,
    )


class ReferralService:
    @staticmethod
    def code_for(user):
        existing = ReferralCode.objects.filter(user=user).first()
        if existing:
            return existing.code
        seed = ''.join(ch for ch in (user.first_name or '').upper() if ch.isalpha())[:4]
        while True:
            code = f'{seed}{_random(8 - len(seed))}'
            if not ReferralCode.objects.filter(code=code).exists():
                return ReferralCode.objects.create(user=user, code=code).code

    @staticmethod
    def can_apply(user):
        if Referral.objects.filter(referee=user).exists():
            return False
        return not Booking.objects.filter(customer=user, status=Booking.Status.COMPLETED).exists()

    @staticmethod
    @transaction.atomic
    def apply(user, code):
        compact = ''.join(ch for ch in (code or '').upper() if ch.isalnum())
        if not compact:
            raise CouponValidationError('Enter a referral code.')
        owner = ReferralCode.objects.select_related('user').filter(code=compact).first()
        if owner is None:
            raise CouponValidationError('This referral code was not found.')
        if owner.user_id == user.pk:
            raise CouponValidationError('You can’t use your own referral code.')
        if Referral.objects.filter(referee=user).exists():
            raise CouponValidationError('You have already used a referral code.')
        if not ReferralService.can_apply(user):
            raise CouponValidationError('Referral codes are only for new customers.')
        coupon = _reward_coupon(owner=user, prefix='WELCOME', title='Referral welcome ₹100 off')
        return Referral.objects.create(referrer=owner.user, referee=user, referee_coupon=coupon)

    @staticmethod
    def on_booking_completed(booking):
        with transaction.atomic():
            referral = (
                Referral.objects.select_for_update()
                .filter(referee_id=booking.customer_id, rewarded_at__isnull=True)
                .first()
            )
            if referral is None:
                return None
            referral.referrer_coupon = _reward_coupon(
                owner=referral.referrer,
                prefix='REFER',
                title='Referral reward ₹100 off',
            )
            referral.rewarded_at = timezone.now()
            referral.save(update_fields=['referrer_coupon', 'rewarded_at', 'updated_at'])
        from apps.accounts.models import UserDeviceToken
        from apps.common.push import send_push

        send_push(
            UserDeviceToken.objects.filter(user_id=referral.referrer_id).values_list('token', flat=True),
            title='You earned ₹100!',
            body=f'Your friend finished their first booking. Use code {referral.referrer_coupon.code} on your next service.',
            data={'type': 'referral_reward'},
        )
        return referral

    @staticmethod
    def summary(user):
        made = Referral.objects.filter(referrer=user)
        coupons = Coupon.objects.filter(owner=user).order_by('-created_at')
        referred = Referral.objects.select_related('referrer').filter(referee=user).first()
        return {
            'code': ReferralService.code_for(user),
            'reward_amount': int(REFERRAL_REWARD),
            'min_order_amount': int(REFERRAL_MIN_ORDER),
            'invited_count': made.count(),
            'rewarded_count': made.filter(rewarded_at__isnull=False).count(),
            'earned_amount': int(REFERRAL_REWARD) * made.filter(rewarded_at__isnull=False).count(),
            'can_apply': referred is None and ReferralService.can_apply(user),
            'applied_code': ReferralService.code_for(referred.referrer) if referred else '',
            'coupons': [
                {
                    'code': coupon.code,
                    'title': coupon.title,
                    'amount': int(coupon.discount_value),
                    'used': coupon.times_used_by(user) > 0,
                }
                for coupon in coupons
            ],
        }
