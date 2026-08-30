from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import FirebaseAuthView, MeView, OTPRequestView, OTPVerifyView

urlpatterns = [
    path('otp/request/', OTPRequestView.as_view(), name='otp-request'),
    path('otp/verify/', OTPVerifyView.as_view(), name='otp-verify'),
    path('firebase/', FirebaseAuthView.as_view(), name='firebase-auth'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='me'),
]
