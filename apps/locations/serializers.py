from rest_framework import serializers

from .models import Address, City


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

    def create(self, validated_data):
        user = self.context['request'].user
        if validated_data.get('is_default'):
            Address.objects.filter(user=user, is_default=True).update(is_default=False)
        return Address.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        if validated_data.get('is_default'):
            Address.objects.filter(user=instance.user, is_default=True).exclude(pk=instance.pk).update(is_default=False)
        return super().update(instance, validated_data)
