from rest_framework import serializers

from apps.catalog.models import ServicePackage
from apps.locations.models import City

from .services import CouponService, CouponValidationError


class CouponOfferSerializer(serializers.Serializer):
    code = serializers.CharField()
    title = serializers.CharField()
    discount_label = serializers.CharField()
    eligible = serializers.BooleanField()


class CouponListQuerySerializer(serializers.Serializer):
    package_id = serializers.UUIDField()
    city_id = serializers.UUIDField(required=False, allow_null=True)


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField()
    package_id = serializers.UUIDField()
    city_id = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.IntegerField(required=False, min_value=1, default=1)

    def validate(self, attrs):
        attrs['code'] = CouponService.normalize_code(attrs.get('code'))
        package = (
            ServicePackage.objects.select_related('service')
            .filter(pk=attrs['package_id'])
            .first()
        )
        if package is None:
            raise serializers.ValidationError(
                {'package_id': 'This service package was not found. Open the service again and retry.'}
            )

        city = None
        city_id = attrs.get('city_id')
        if city_id:
            city = City.objects.filter(pk=city_id).first()

        user = self.context['request'].user
        try:
            coupon, subtotal, discount, total = CouponService.validate(
                user=user,
                code=attrs['code'],
                package=package,
                city=city,
                quantity=attrs.get('quantity', 1),
            )
        except CouponValidationError as exc:
            raise serializers.ValidationError({'code': exc.message}) from exc
        attrs['package'] = package
        attrs['city'] = city
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
