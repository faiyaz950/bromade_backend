from datetime import date
from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import CityPackagePrice, ServicePackage
from apps.coupons.services import CouponService, CouponValidationError
from apps.locations.models import Address

from .models import Booking, BookingItem


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

    class Meta:
        model = Booking
        fields = (
            'id',
            'scheduled_date',
            'scheduled_time',
            'status',
            'subtotal_amount',
            'discount_amount',
            'total_amount',
            'coupon_code',
            'payment_method',
            'notes',
            'items',
            'created_at',
        )

    def get_payment_method(self, obj):
        latest_payment = max(obj.payments.all(), default=None, key=lambda p: p.created_at)
        return latest_payment.method if latest_payment else None


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
