from django.db.models import Avg, Count
from django.utils import timezone

from rest_framework import serializers

from apps.bookings.models import Booking, BookingAssignment, BookingItem
from apps.catalog.models import Service
from apps.locations.models import City
from apps.partners.models import PartnerCity, PartnerDeviceToken, PartnerProfile, PartnerService, PartnerUnavailableDate
from apps.payments.models import Payment


def _digits(value):
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def _last4(value):
    digits = _digits(value)
    return digits[-4:] if len(digits) >= 4 else ''


class PartnerProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    cities = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    city_ids = serializers.SerializerMethodField()
    service_ids = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    approval_note = serializers.CharField(read_only=True)
    registration_complete = serializers.SerializerMethodField()
    aadhaar_last4 = serializers.SerializerMethodField()
    bank_account_last4 = serializers.SerializerMethodField()

    class Meta:
        model = PartnerProfile
        fields = (
            'id',
            'full_name',
            'phone_number',
            'email',
            'address_line',
            'pincode',
            'years_experience',
            'pan_number',
            'upi_id',
            'upi_phone',
            'bank_account_holder',
            'bank_ifsc',
            'aadhaar_last4',
            'bank_account_last4',
            'is_active',
            'is_available_for_assignment',
            'approval_status',
            'approval_note',
            'registration_complete',
            'cities',
            'services',
            'city_ids',
            'service_ids',
            'average_rating',
            'rating_count',
            'wallet_balance',
        )
        read_only_fields = fields

    def get_cities(self, obj):
        return [pc.city.name for pc in obj.cities.select_related('city')]

    def get_services(self, obj):
        return [ps.service.name for ps in obj.services.select_related('service')]

    def get_city_ids(self, obj):
        return [str(pc.city_id) for pc in obj.cities.all()]

    def get_service_ids(self, obj):
        return [str(ps.service_id) for ps in obj.services.all()]

    def get_registration_complete(self, obj):
        return obj.registration_is_complete

    def get_aadhaar_last4(self, obj):
        return _last4(obj.aadhaar_number)

    def get_bank_account_last4(self, obj):
        return _last4(obj.bank_account_number)

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


class PartnerRegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.CharField(required=False, allow_blank=True, max_length=254)
    address_line = serializers.CharField(max_length=255)
    pincode = serializers.CharField(max_length=10)
    years_experience = serializers.IntegerField(required=False, default=0)
    aadhaar_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    pan_number = serializers.CharField(required=False, allow_blank=True, max_length=16)
    upi_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    upi_phone = serializers.CharField(required=False, allow_blank=True, max_length=15)
    bank_account_holder = serializers.CharField(required=False, allow_blank=True, max_length=150)
    bank_account_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    bank_ifsc = serializers.CharField(required=False, allow_blank=True, max_length=15)
    city_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    service_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)

    def validate_email(self, value):
        email = (value or '').strip()
        if not email:
            return ''
        try:
            return serializers.EmailField().run_validation(email)
        except serializers.ValidationError:
            raise serializers.ValidationError('Enter a valid email, or leave it blank.')

    def validate_years_experience(self, value):
        try:
            years = int(value or 0)
        except (TypeError, ValueError):
            return 0
        return max(0, min(years, 50))

    def validate_pincode(self, value):
        digits = _digits(value)
        if len(digits) != 6:
            raise serializers.ValidationError('Enter a 6-digit pincode.')
        return digits

    def validate_aadhaar_number(self, value):
        if not value:
            return ''
        digits = _digits(value)
        if len(digits) != 12:
            raise serializers.ValidationError('Enter a 12-digit Aadhaar number.')
        return digits

    def validate_pan_number(self, value):
        pan = (value or '').strip().upper().replace(' ', '')
        if len(pan) != 10:
            return ''
        return pan

    def validate_upi_phone(self, value):
        digits = _digits(value)
        if len(digits) != 10:
            return ''
        return digits

    def validate_upi_id(self, value):
        upi = (value or '').strip().lower()
        if not upi or '@' not in upi:
            return ''
        return upi

    def validate_bank_ifsc(self, value):
        ifsc = (value or '').strip().upper().replace(' ', '')
        if len(ifsc) != 11:
            return ''
        return ifsc

    def validate_city_ids(self, value):
        cities = list(City.objects.filter(id__in=value, is_active=True))
        if len(cities) != len(set(value)):
            raise serializers.ValidationError('Choose at least one live service city.')
        return cities

    def validate_service_ids(self, value):
        services = list(Service.objects.filter(id__in=value, is_active=True))
        if len(services) != len(set(value)):
            raise serializers.ValidationError('Choose at least one service you can deliver.')
        return services

    def validate(self, attrs):
        partner = self.context['partner']
        aadhaar = attrs.get('aadhaar_number') or partner.aadhaar_number
        if len(_digits(aadhaar)) != 12:
            raise serializers.ValidationError({'aadhaar_number': 'Enter a 12-digit Aadhaar number.'})
        attrs['aadhaar_number'] = _digits(aadhaar)
        return attrs

    def save(self, **kwargs):
        partner = self.context['partner']
        data = self.validated_data
        partner.full_name = data['full_name'].strip()
        partner.email = data.get('email', '') or ''
        partner.address_line = data['address_line'].strip()
        partner.pincode = data['pincode']
        partner.years_experience = data.get('years_experience') or 0
        if data.get('aadhaar_number'):
            partner.aadhaar_number = data['aadhaar_number']
        partner.pan_number = data.get('pan_number', '') or partner.pan_number
        if data.get('upi_id') is not None:
            partner.upi_id = data.get('upi_id') or partner.upi_id
        if data.get('upi_phone') is not None:
            partner.upi_phone = data.get('upi_phone') or partner.upi_phone
        if data.get('bank_account_holder'):
            partner.bank_account_holder = data['bank_account_holder']
        if data.get('bank_account_number'):
            partner.bank_account_number = _digits(data['bank_account_number'])
        if data.get('bank_ifsc'):
            partner.bank_ifsc = data['bank_ifsc']
        if partner.approval_status == PartnerProfile.ApprovalStatus.REJECTED:
            partner.approval_status = PartnerProfile.ApprovalStatus.PENDING
            partner.approval_note = ''
        partner.save()

        PartnerCity.objects.filter(partner=partner).exclude(
            city__in=data['city_ids']
        ).delete()
        for city in data['city_ids']:
            PartnerCity.objects.get_or_create(partner=partner, city=city)
        PartnerService.objects.filter(partner=partner).exclude(
            service__in=data['service_ids']
        ).delete()
        for service in data['service_ids']:
            PartnerService.objects.get_or_create(partner=partner, service=service)
        return partner


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
    commission_amount = serializers.SerializerMethodField()
    can_accept = serializers.SerializerMethodField()
    low_wallet_balance = serializers.SerializerMethodField()

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
            'commission_amount',
            'can_accept',
            'low_wallet_balance',
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

    def get_commission_amount(self, obj):
        from apps.partners.wallet_service import commission_amount

        return commission_amount(obj.total_amount)

    def _wallet_covers_commission(self, obj):
        partner = self.context.get('partner')
        if partner is None:
            return False
        from apps.partners.wallet_service import commission_amount, money

        return money(partner.wallet_balance) >= commission_amount(obj.total_amount)

    def get_can_accept(self, obj):
        assignment = self._assignment(obj)
        if assignment is None or assignment.status != BookingAssignment.Status.PENDING:
            return False
        return self._wallet_covers_commission(obj)

    def get_low_wallet_balance(self, obj):
        assignment = self._assignment(obj)
        if assignment is None or assignment.status != BookingAssignment.Status.PENDING:
            return False
        return not self._wallet_covers_commission(obj)


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
