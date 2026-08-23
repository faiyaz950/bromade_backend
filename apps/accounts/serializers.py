from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.customers.models import CustomerProfile

from .models import User
from .services.otp import OTPService


class OTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)

    def create(self, validated_data):
        return OTPService().request_otp(validated_data['phone_number'])


class OTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate(self, attrs):
        try:
            OTPService().verify_otp(attrs['phone_number'], attrs['code'])
        except ValueError as exc:
            raise serializers.ValidationError({'code': str(exc)}) from exc
        return attrs

    def create(self, validated_data):
        user, created = User.objects.get_or_create(
            phone_number=validated_data['phone_number'],
            defaults={
                'first_name': validated_data.get('first_name', ''),
                'last_name': validated_data.get('last_name', ''),
            },
        )
        if not created:
            updated = False
            for field in ('first_name', 'last_name'):
                incoming = validated_data.get(field)
                if incoming and getattr(user, field) != incoming:
                    setattr(user, field, incoming)
                    updated = True
            if updated:
                user.save(update_fields=['first_name', 'last_name', 'updated_at'])

        CustomerProfile.objects.get_or_create(
            user=user,
            defaults={'full_name': f'{user.first_name} {user.last_name}'.strip()},
        )

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': user,
            'is_new_user': created,
        }


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'phone_number', 'first_name', 'last_name', 'full_name')

    def get_full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip()
