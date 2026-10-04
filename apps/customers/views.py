from django.conf import settings
from rest_framework import generics, response, serializers

from apps.bookings.models import Booking

from .models import SupportTicket


class SupportTicketSerializer(serializers.ModelSerializer):
    booking_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    booking = serializers.UUIDField(source='booking_id', read_only=True)

    class Meta:
        model = SupportTicket
        fields = ('id', 'booking', 'booking_id', 'topic', 'message', 'status', 'reply', 'created_at')
        read_only_fields = ('id', 'status', 'reply', 'created_at')

    def validate_booking_id(self, value):
        if value is None:
            return None
        booking = Booking.objects.filter(pk=value, customer=self.context['request'].user).first()
        if booking is None:
            raise serializers.ValidationError('Booking not found.')
        return booking

    def create(self, validated_data):
        booking = validated_data.pop('booking_id', None)
        return SupportTicket.objects.create(user=self.context['request'].user, booking=booking, **validated_data)


class SupportTicketListView(generics.ListCreateAPIView):
    serializer_class = SupportTicketSerializer
    pagination_class = None

    def get_queryset(self):
        qs = SupportTicket.objects.filter(user=self.request.user)
        booking = self.request.query_params.get('booking')
        if booking:
            qs = qs.filter(booking_id=booking)
        return qs[:50]


class SupportContactView(generics.GenericAPIView):
    def get(self, request):
        return response.Response(
            {
                'phone': settings.SUPPORT_PHONE,
                'whatsapp': settings.SUPPORT_WHATSAPP,
                'email': settings.SUPPORT_EMAIL,
                'hours': settings.SUPPORT_HOURS,
            }
        )
