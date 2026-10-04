from rest_framework import generics, permissions, response, status

from .models import UserDeviceToken
from .serializers import (
    DeviceTokenSerializer,
    EmailLoginSerializer,
    EmailRegisterSerializer,
    FirebaseAuthSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    UserSerializer,
)


class OTPRequestView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = OTPRequestSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp_request = serializer.save()
        return response.Response(
            {
                'message': 'OTP generated successfully.',
                'phone_number': otp_request.phone_number,
                'otp_code': otp_request.code,
                'expires_at': otp_request.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


class OTPVerifyView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = OTPVerifySerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        return response.Response(
            {
                'access': payload['access'],
                'refresh': payload['refresh'],
                'is_new_user': payload['is_new_user'],
                'user': UserSerializer(payload['user']).data,
            }
        )


class FirebaseAuthView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = FirebaseAuthSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        return response.Response(
            {
                'access': payload['access'],
                'refresh': payload['refresh'],
                'is_new_user': payload['is_new_user'],
                'user': UserSerializer(payload['user']).data,
            }
        )


def _auth_response(payload, *, created_status=False):
    body = {
        'access': payload['access'],
        'refresh': payload['refresh'],
        'is_new_user': payload['is_new_user'],
        'user': UserSerializer(payload['user']).data,
    }
    if created_status:
        return response.Response(body, status=status.HTTP_201_CREATED)
    return response.Response(body)


class EmailRegisterView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmailRegisterSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        return _auth_response(payload, created_status=True)


class EmailLoginView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = EmailLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        return _auth_response(payload)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class DeviceTokenView(generics.GenericAPIView):
    """Register (POST) or forget (DELETE) this phone's push token."""

    serializer_class = DeviceTokenSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        UserDeviceToken.objects.update_or_create(
            token=serializer.validated_data['token'],
            defaults={'user': request.user, 'platform': serializer.validated_data['platform']},
        )
        return response.Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request):
        token = request.data.get('token') or request.query_params.get('token')
        if token:
            UserDeviceToken.objects.filter(user=request.user, token=token).delete()
        return response.Response(status=status.HTTP_204_NO_CONTENT)
