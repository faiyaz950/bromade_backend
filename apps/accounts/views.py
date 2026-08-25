from rest_framework import generics, permissions, response, status

from .serializers import FirebaseAuthSerializer, OTPRequestSerializer, OTPVerifySerializer, UserSerializer


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


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
