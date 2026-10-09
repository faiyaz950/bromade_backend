from decimal import Decimal

from rest_framework import serializers

from .models import Address, City
from .services import haversine_km


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ('id', 'name', 'slug', 'state')


class CoverageCheckSerializer(serializers.Serializer):
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    city_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    place_names = serializers.ListField(
        child=serializers.CharField(max_length=120),
        required=False,
        allow_empty=True,
    )
    city_id = serializers.UUIDField(required=False)


class AddressSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)
    city_id = serializers.PrimaryKeyRelatedField(source='city', queryset=City.objects.filter(is_active=True), write_only=True)
    latitude = serializers.FloatField(required=False, allow_null=True, min_value=-90, max_value=90)
    longitude = serializers.FloatField(required=False, allow_null=True, min_value=-180, max_value=180)

    class Meta:
        model = Address
        fields = (
            'id',
            'label',
            'contact_name',
            'contact_phone',
            'line1',
            'line2',
            'landmark',
            'pincode',
            'latitude',
            'longitude',
            'is_default',
            'city',
            'city_id',
        )

    def validate(self, attrs):
        latitude = attrs.get('latitude', getattr(self.instance, 'latitude', None))
        longitude = attrs.get('longitude', getattr(self.instance, 'longitude', None))
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError({'latitude': 'Send both latitude and longitude.'})
        # The model keeps 6 decimal places (~10 cm); GPS gives more.
        for key in ('latitude', 'longitude'):
            if attrs.get(key) is not None:
                attrs[key] = Decimal(str(round(attrs[key], 6)))

        city = attrs.get('city') or getattr(self.instance, 'city', None)
        if latitude is not None and city is not None and city.latitude is not None and city.longitude is not None:
            distance = haversine_km(float(latitude), float(longitude), float(city.latitude), float(city.longitude))
            if distance > (city.service_radius_km or 0):
                raise serializers.ValidationError(
                    {'latitude': f'This pin is outside our {city.name} service area. Move the pin or pick another city.'}
                )
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        if validated_data.get('is_default'):
            Address.objects.filter(user=user, is_default=True).update(is_default=False)
        return Address.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        if validated_data.get('is_default'):
            Address.objects.filter(user=instance.user, is_default=True).exclude(pk=instance.pk).update(is_default=False)
        return super().update(instance, validated_data)
