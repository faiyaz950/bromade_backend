from rest_framework import serializers

from .models import User
from .services.firebase import verify_id_token
from .services.otp import OTPService
from .services.session import issue_auth_payload, issue_firebase_auth_payload


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
        return issue_auth_payload(
            phone_number=validated_data['phone_number'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )


class FirebaseAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate(self, attrs):
        try:
            decoded = verify_id_token(attrs['id_token'])
        except Exception as exc:
            raise serializers.ValidationError({'id_token': 'Invalid or expired Firebase token.'}) from exc
        phone_number = decoded.get('phone_number')
        email = decoded.get('email')
        firebase_uid = decoded.get('user_id') or decoded.get('uid') or decoded.get('sub')
        if not phone_number and not email and not firebase_uid:
            raise serializers.ValidationError(
                {'id_token': 'Firebase token has no email or phone number.'}
            )
        attrs['decoded'] = decoded
        return attrs

    def create(self, validated_data):
        try:
            return issue_firebase_auth_payload(
                validated_data['decoded'],
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
            )
        except ValueError as exc:
            raise serializers.ValidationError({'id_token': str(exc)}) from exc


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'phone_number', 'email', 'first_name', 'last_name', 'full_name')
        read_only_fields = ('id', 'phone_number', 'email', 'full_name')

    def get_full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip()

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        profile = getattr(instance, 'customer_profile', None)
        if profile is not None:
            profile.full_name = f'{instance.first_name} {instance.last_name}'.strip()
            profile.save(update_fields=['full_name', 'updated_at'])
        return instance
