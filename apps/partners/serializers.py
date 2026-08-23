from rest_framework import serializers

from apps.bookings.models import Booking, BookingAssignment, BookingItem
from apps.partners.models import PartnerProfile


class PartnerProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    cities = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()

    class Meta:
        model = PartnerProfile
        fields = (
            'id',
            'full_name',
            'phone_number',
            'is_active',
            'is_available_for_assignment',
            'approval_status',
            'cities',
            'services',
        )
        read_only_fields = ('id', 'full_name', 'phone_number', 'is_active', 'cities', 'services')

    def get_cities(self, obj):
        return [pc.city.name for pc in obj.cities.select_related('city')]

    def get_services(self, obj):
        return [ps.service.name for ps in obj.services.select_related('service')]


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
    city_name = serializers.CharField(source='city.name', read_only=True)
    assignment_id = serializers.SerializerMethodField()
    assignment_status = serializers.CharField(read_only=True)
    payment_method = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            'id',
            'assignment_id',
            'assignment_status',
            'status',
            'scheduled_date',
            'scheduled_time',
            'total_amount',
            'payment_method',
            'notes',
            'customer_name',
            'customer_phone',
            'address_label',
            'address_line',
            'city_name',
            'items',
            'created_at',
        )

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
        return ', '.join(parts)

    def get_payment_method(self, obj):
        latest_payment = max(obj.payments.all(), default=None, key=lambda p: p.created_at)
        return latest_payment.method if latest_payment else None

    def get_assignment_id(self, obj):
        assignment = self.context.get('assignment')
        if assignment:
            return str(assignment.id)
        latest = obj.assignments.filter(partner=self.context.get('partner')).order_by('-assigned_at').first()
        return str(latest.id) if latest else None


class PartnerJobRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)
