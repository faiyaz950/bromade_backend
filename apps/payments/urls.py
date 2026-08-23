from django.urls import path

from .views import PaymentOrderCreateView, PaymentVerifyView, RazorpayWebhookView

urlpatterns = [
    path('orders/', PaymentOrderCreateView.as_view(), name='payment-order-create'),
    path('verify/', PaymentVerifyView.as_view(), name='payment-verify'),
    path('webhooks/razorpay/', RazorpayWebhookView.as_view(), name='razorpay-webhook'),
]
