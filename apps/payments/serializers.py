from rest_framework import serializers

from apps.bookings.models import Booking

from .models import Payment


class PaymentOrderSerializer(serializers.Serializer):
    booking_id = serializers.PrimaryKeyRelatedField(source='booking', queryset=Booking.objects.all())
    method = serializers.ChoiceField(choices=Payment.Method.choices, default=Payment.Method.ONLINE)

    def validate(self, attrs):
        booking = attrs['booking']
        user = self.context['request'].user
        if booking.customer_id != user.id:
            raise serializers.ValidationError({'booking_id': 'This booking does not belong to the current user.'})
        return attrs


class PaymentVerifySerializer(serializers.Serializer):
    gateway_order_id = serializers.CharField(max_length=120)
    gateway_payment_id = serializers.CharField(max_length=120)
    signature = serializers.CharField(max_length=255, required=False, allow_blank=True)
