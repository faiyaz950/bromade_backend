from rest_framework import serializers

from apps.catalog.models import ServicePackage
from apps.locations.models import City

from .services import CouponService, CouponValidationError


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField()
    package_id = serializers.PrimaryKeyRelatedField(
        source='package',
        queryset=ServicePackage.objects.filter(is_active=True),
    )
    city_id = serializers.PrimaryKeyRelatedField(
        source='city',
        queryset=City.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    quantity = serializers.IntegerField(required=False, min_value=1, default=1)

    def validate(self, attrs):
        user = self.context['request'].user
        try:
            coupon, subtotal, discount, total = CouponService.validate(
                user=user,
                code=attrs['code'],
                package=attrs['package'],
                city=attrs.get('city'),
                quantity=attrs.get('quantity', 1),
            )
        except CouponValidationError as exc:
            raise serializers.ValidationError({'code': exc.message}) from exc
        attrs['coupon'] = coupon
        attrs['subtotal_amount'] = subtotal
        attrs['discount_amount'] = discount
        attrs['total_amount'] = total
        return attrs

    def to_representation(self, instance):
        coupon = instance['coupon']
        discount = instance['discount_amount']
        return {
            'valid': True,
            'code': coupon.code,
            'title': coupon.title,
            'discount_type': coupon.discount_type,
            'discount_value': coupon.discount_value,
            'discount_amount': discount,
            'subtotal_amount': instance['subtotal_amount'],
            'total_amount': instance['total_amount'],
            'currency': 'INR',
            'message': f'{coupon.title} applied. You save ₹{discount:.0f}.',
        }
