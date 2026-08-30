from django.db.models import Avg, Count
from django.utils import timezone

from rest_framework import serializers

from apps.bookings.models import Booking, BookingAssignment, BookingItem
from apps.partners.models import PartnerDeviceToken, PartnerProfile, PartnerUnavailableDate
from apps.payments.models import Payment


class PartnerProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    cities = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    approval_note = serializers.CharField(read_only=True)

    class Meta:
        model = PartnerProfile
        fields = (
            'id',
            'full_name',
            'phone_number',
            'is_active',
            'is_available_for_assignment',
            'approval_status',
            'approval_note',
            'cities',
            'services',
            'average_rating',
            'rating_count',
        )
        read_only_fields = (
            'id',
            'full_name',
            'phone_number',
            'is_active',
            'cities',
            'services',
            'approval_status',
            'approval_note',
            'average_rating',
            'rating_count',
        )

    def get_cities(self, obj):
        return [pc.city.name for pc in obj.cities.select_related('city')]

    def get_services(self, obj):
        return [ps.service.name for ps in obj.services.select_related('service')]

    def _rating_stats(self, obj):
        cached = getattr(obj, '_rating_stats', None)
        if cached is not None:
            return cached
        stats = Booking.objects.filter(
            assignments__partner=obj,
            assignments__status=BookingAssignment.Status.ACCEPTED,
            rating__isnull=False,
        ).aggregate(avg=Avg('rating__stars'), count=Count('rating'))
        obj._rating_stats = stats
        return stats

    def get_average_rating(self, obj):
        avg = self._rating_stats(obj)['avg']
        return round(float(avg), 1) if avg else None

    def get_rating_count(self, obj):
        return self._rating_stats(obj)['count'] or 0


class PartnerAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerProfile
        fields = ('is_available_for_assignment',)


class PartnerJobItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingItem
        fields = ('service_name', 'package_name', 'unit_price', 'quantity', 'line_total')


class PartnerJobSerializer(serializers.ModelSerializer):
    items = PartnerJobItemSerializer(many=True, read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.CharField(source='customer.phone_number', read_only=True)
    address_label = serializers.CharField(source='address.label', read_only=True)
    address_line = serializers.SerializerMethodField()
    address_latitude = serializers.DecimalField(
        source='address.latitude',
        max_digits=9,
        decimal_places=6,
        read_only=True,
        allow_null=True,
    )
    address_longitude = serializers.DecimalField(
        source='address.longitude',
        max_digits=9,
        decimal_places=6,
        read_only=True,
        allow_null=True,
    )
    city_name = serializers.CharField(source='city.name', read_only=True)
    assignment_id = serializers.SerializerMethodField()
    assignment_status = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    cash_collected = serializers.SerializerMethodField()
    rating_stars = serializers.SerializerMethodField()
    rating_comment = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            'id',
            'assignment_id',
            'assignment_status',
            'status',
            'visit_status',
            'checklist',
            'scheduled_date',
            'scheduled_time',
            'total_amount',
            'payment_method',
            'payment_status',
            'cash_collected',
            'notes',
            'customer_name',
            'customer_phone',
            'address_label',
            'address_line',
            'address_latitude',
            'address_longitude',
            'city_name',
            'rating_stars',
            'rating_comment',
            'items',
            'created_at',
        )

    def _assignment(self, obj):
        assignment = self.context.get('assignment')
        if assignment:
            return assignment
        partner = self.context.get('partner')
        if partner is None:
            return None
        return obj.assignments.filter(partner=partner).order_by('-assigned_at').first()

    def _payment(self, obj):
        return max(obj.payments.all(), default=None, key=lambda p: p.created_at)

    def get_customer_name(self, obj):
        profile = getattr(obj.customer, 'customer_profile', None)
        if profile and profile.full_name:
            return profile.full_name
        name = f'{obj.customer.first_name} {obj.customer.last_name}'.strip()
        return name or obj.customer.phone_number

    def get_address_line(self, obj):
        parts = [obj.address.line1]
        if obj.address.line2:
            parts.append(obj.address.line2)
        if obj.address.landmark:
            parts.append(obj.address.landmark)
        return ', '.join(parts)

    def get_payment_method(self, obj):
        payment = self._payment(obj)
        return payment.method if payment else None

    def get_payment_status(self, obj):
        payment = self._payment(obj)
        return payment.status if payment else None

    def get_cash_collected(self, obj):
        payment = self._payment(obj)
        return bool(
            payment
            and payment.method == Payment.Method.CASH
            and payment.status == Payment.Status.PAID
        )

    def get_assignment_id(self, obj):
        assignment = self._assignment(obj)
        return str(assignment.id) if assignment else None

    def get_assignment_status(self, obj):
        assignment = self._assignment(obj)
        return assignment.status if assignment else obj.assignment_status

    def get_rating_stars(self, obj):
        rating = getattr(obj, 'rating', None)
        return rating.stars if rating else None

    def get_rating_comment(self, obj):
        rating = getattr(obj, 'rating', None)
        return rating.comment if rating else ''


class PartnerJobRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class PartnerVisitActionSerializer(serializers.Serializer):
    visit_status = serializers.ChoiceField(
        choices=[
            Booking.VisitStatus.ON_THE_WAY,
            Booking.VisitStatus.ARRIVED,
            Booking.VisitStatus.IN_PROGRESS,
            Booking.VisitStatus.COMPLETED,
        ]
    )
    checklist = serializers.ListField(child=serializers.DictField(), required=False)


class PartnerDeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerDeviceToken
        fields = ('token', 'platform')


class PartnerUnavailableDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerUnavailableDate
        fields = ('id', 'date', 'note')
        read_only_fields = ('id',)

    def validate_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError('Date cannot be in the past.')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        partner = getattr(getattr(request, 'user', None), 'partner_profile', None)
        date = attrs.get('date')
        if partner and date:
            exists = PartnerUnavailableDate.objects.filter(partner=partner, date=date)
            if self.instance:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                raise serializers.ValidationError({'date': 'This date is already blocked.'})
        return attrs
