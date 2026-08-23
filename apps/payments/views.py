from rest_framework import generics, response, status

from .models import Payment
from .serializers import PaymentOrderSerializer, PaymentVerifySerializer
from .services import CashPaymentService, RazorpayGatewayService


class PaymentOrderCreateView(generics.GenericAPIView):
    serializer_class = PaymentOrderSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = serializer.validated_data['booking']
        method = serializer.validated_data['method']

        if method == Payment.Method.CASH:
            payment = CashPaymentService.create_order(booking)
        else:
            payment = RazorpayGatewayService.create_order(booking)

        return response.Response(
            {
                'payment_id': str(payment.id),
                'gateway': payment.gateway,
                'gateway_order_id': payment.gateway_order_id,
                'method': payment.method,
                'amount': payment.amount,
                'currency': payment.currency,
                'status': payment.status,
                'booking_status': payment.booking.status,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentVerifyView(generics.GenericAPIView):
    serializer_class = PaymentVerifySerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = generics.get_object_or_404(Payment, gateway_order_id=serializer.validated_data['gateway_order_id'])
        if payment.booking.customer_id != request.user.id:
            return response.Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        payment = RazorpayGatewayService.verify_payment(
            payment,
            serializer.validated_data['gateway_payment_id'],
            serializer.validated_data.get('signature', ''),
        )
        return response.Response({'status': payment.status, 'booking_status': payment.booking.status})


class RazorpayWebhookView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        return response.Response({'received': True, 'mode': 'mock'})
