from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count
from rest_framework import serializers

from apps.catalog.models import CityPackagePrice, ServicePackage
from apps.coupons.services import CouponService, CouponValidationError
from apps.locations.models import Address

from .models import Booking, BookingAssignment, BookingItem

TIMELINE_KEYS = ('on_the_way', 'arrived', 'in_progress', 'cash_collected', 'completed')


def photo_url(field, request):
    if not field:
        return None
    try:
        url = field.url
    except ValueError:
        return None
    return request.build_absolute_uri(url) if request else url


def latest_payment(booking):
    return max(booking.payments.all(), default=None, key=lambda p: p.created_at)


def is_cash_collected(booking):
    payment = latest_payment(booking)
    return bool(payment and payment.method == 'cash' and payment.status == 'paid')


def booking_timeline(booking, accepted_assignment=None):
    """ISO timestamps for each visit milestone the booking has reached."""
    timeline = {'booked': booking.created_at.isoformat()}
    if accepted_assignment is not None and accepted_assignment.responded_at:
        timeline['assigned'] = accepted_assignment.responded_at.isoformat()
    for log in booking.status_logs.all():
        if log.to_status in TIMELINE_KEYS:
            timeline[log.to_status] = log.created_at.isoformat()
    return timeline


class BookingDraftSerializer(serializers.Serializer):
    package_id = serializers.PrimaryKeyRelatedField(source='package', queryset=ServicePackage.objects.filter(is_active=True))
    address_id = serializers.PrimaryKeyRelatedField(source='address', queryset=Address.objects.all())
    scheduled_date = serializers.DateField()
    scheduled_time = serializers.TimeField()
    notes = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.IntegerField(required=False, min_value=1, default=1)
    coupon_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_scheduled_date(self, value):
        if value < date.today():
            raise serializers.ValidationError('Scheduled date cannot be in the past.')
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        if attrs['address'].user_id != user.id:
            raise serializers.ValidationError({'address_id': 'This address does not belong to the current user.'})
        if not attrs['address'].city.is_active:
            raise serializers.ValidationError(
                {'address_id': 'Services are not available in this city yet.'}
            )
        code = CouponService.normalize_code(attrs.pop('coupon_code', '') or '')
        if code:
            try:
                coupon, _subtotal, _discount, _total = CouponService.validate(
                    user=user,
                    code=code,
                    package=attrs['package'],
                    city=attrs['address'].city,
                    quantity=attrs.get('quantity', 1),
                )
            except CouponValidationError as exc:
                raise serializers.ValidationError({'coupon_code': exc.message}) from exc
            attrs['coupon'] = coupon
        return attrs


class BookingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingItem
        fields = ('id', 'service_name', 'package_name', 'unit_price', 'quantity', 'line_total')


class BookingSerializer(serializers.ModelSerializer):
    items = BookingItemSerializer(many=True, read_only=True)
    payment_method = serializers.SerializerMethodField()
    rating_stars = serializers.SerializerMethodField()
    rating_comment = serializers.SerializerMethodField()
    partner_name = serializers.SerializerMethodField()
    partner_phone = serializers.SerializerMethodField()
    partner_average_rating = serializers.SerializerMethodField()
    partner_rating_count = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    cash_collected = serializers.SerializerMethodField()
    start_photo_url = serializers.SerializerMethodField()
    completion_photo_url = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            'id',
            'scheduled_date',
            'scheduled_time',
            'status',
            'visit_status',
            'assignment_status',
            'payment_status',
            'cash_collected',
            'start_photo_url',
            'completion_photo_url',
            'timeline',
            'partner_name',
            'partner_phone',
            'partner_average_rating',
            'partner_rating_count',
            'subtotal_amount',
            'discount_amount',
            'total_amount',
            'coupon_code',
            'payment_method',
            'rating_stars',
            'rating_comment',
            'notes',
            'items',
            'created_at',
        )

    def _accepted_assignment(self, obj):
        assignments = list(obj.assignments.all())
        return next((a for a in assignments if a.status == BookingAssignment.Status.ACCEPTED), None)

    def get_payment_method(self, obj):
        payment = latest_payment(obj)
        return payment.method if payment else None

    def get_payment_status(self, obj):
        payment = latest_payment(obj)
        return payment.status if payment else None

    def get_cash_collected(self, obj):
        return is_cash_collected(obj)

    def get_start_photo_url(self, obj):
        return photo_url(obj.start_photo, self.context.get('request'))

    def get_completion_photo_url(self, obj):
        return photo_url(obj.completion_photo, self.context.get('request'))

    def get_timeline(self, obj):
        return booking_timeline(obj, self._accepted_assignment(obj))

    def get_rating_stars(self, obj):
        rating = getattr(obj, 'rating', None)
        return rating.stars if rating else None

    def get_rating_comment(self, obj):
        rating = getattr(obj, 'rating', None)
        return rating.comment if rating else ''

    def get_partner_name(self, obj):
        assignment = self._accepted_assignment(obj)
        if assignment is None:
            return ''
        return assignment.partner.full_name or 'Bayti professional'

    def get_partner_phone(self, obj):
        assignment = self._accepted_assignment(obj)
        if assignment is None:
            return ''
        return assignment.partner.user.phone_number or ''

    def _partner_rating_stats(self, obj):
        assignment = self._accepted_assignment(obj)
        if assignment is None:
            return {'avg': None, 'count': 0}
        partner = assignment.partner
        cached = getattr(partner, '_rating_stats', None)
        if cached is not None:
            return cached
        stats = Booking.objects.filter(
            assignments__partner=partner,
            assignments__status=BookingAssignment.Status.ACCEPTED,
            rating__isnull=False,
        ).aggregate(avg=Avg('rating__stars'), count=Count('rating'))
        partner._rating_stats = stats
        return stats

    def get_partner_average_rating(self, obj):
        avg = self._partner_rating_stats(obj)['avg']
        return round(float(avg), 1) if avg else None

    def get_partner_rating_count(self, obj):
        return self._partner_rating_stats(obj)['count'] or 0


class BookingRatingSerializer(serializers.Serializer):
    stars = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=400)


class BookingPriceSummarySerializer(serializers.Serializer):
    package_id = serializers.UUIDField()
    city_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        try:
            package = ServicePackage.objects.get(pk=attrs['package_id'], is_active=True)
        except ServicePackage.DoesNotExist as exc:
            raise serializers.ValidationError({'package_id': 'Invalid package.'}) from exc
        attrs['package'] = package
        return attrs

    def to_representation(self, instance):
        package = self.validated_data['package']
        city_id = self.validated_data.get('city_id')
        city_price = CityPackagePrice.objects.filter(package=package, city_id=city_id, is_active=True).first() if city_id else None
        base_price = city_price.price if city_price else package.base_price
        discounted_price = city_price.discounted_price if city_price else package.discounted_price
        return {
            'package_id': str(package.id),
            'package_name': package.name,
            'base_price': base_price,
            'discounted_price': discounted_price,
            'currency': 'INR',
            'savings': Decimal(base_price) - Decimal(discounted_price),
        }
