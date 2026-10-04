from django.conf import settings
from django.db.models import Count, F, Q
from rest_framework import generics, response, serializers, status

from apps.bookings.models import Booking

from .models import SupportMessage, SupportTicket
from .support import SupportService


class SupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = ('id', 'sender', 'body', 'created_at')


class SupportTicketSerializer(serializers.ModelSerializer):
    booking = serializers.UUIDField(source='booking_id', read_only=True)
    booking_label = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = (
            'id',
            'booking',
            'booking_label',
            'topic',
            'status',
            'last_message',
            'last_message_at',
            'unread_count',
            'created_at',
        )

    def get_booking_label(self, obj):
        booking = obj.booking
        if booking is None:
            return ''
        item = next(iter(booking.items.all()), None)
        return f'{item.package_name if item else "Booking"} · {str(booking.id)[:8].upper()}'

    def get_last_message(self, obj):
        message = obj.messages.order_by('-created_at').first()
        return SupportMessageSerializer(message).data if message else None

    def get_unread_count(self, obj):
        return obj.unread_for_customer()


class SupportTicketDetailSerializer(SupportTicketSerializer):
    messages = SupportMessageSerializer(many=True, read_only=True)

    class Meta(SupportTicketSerializer.Meta):
        fields = SupportTicketSerializer.Meta.fields + ('messages',)


class StartChatSerializer(serializers.Serializer):
    topic = serializers.CharField(max_length=80)
    message = serializers.CharField(max_length=2000)
    booking_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_booking_id(self, value):
        if value is None:
            return None
        booking = Booking.objects.filter(pk=value, customer=self.context['request'].user).first()
        if booking is None:
            raise serializers.ValidationError('Booking not found.')
        return booking


def _tickets(user):
    return SupportTicket.objects.filter(user=user).select_related('booking').prefetch_related('booking__items')


class SupportTicketListView(generics.GenericAPIView):
    def get(self, request):
        qs = _tickets(request.user)
        booking = request.query_params.get('booking')
        if booking:
            qs = qs.filter(booking_id=booking)
        return response.Response(SupportTicketSerializer(qs[:50], many=True).data)

    def post(self, request):
        data = StartChatSerializer(data=request.data, context={'request': request})
        data.is_valid(raise_exception=True)
        ticket = SupportService.start_chat(
            user=request.user,
            topic=data.validated_data['topic'],
            body=data.validated_data['message'],
            booking=data.validated_data.get('booking_id'),
        )
        return response.Response(SupportTicketDetailSerializer(ticket).data, status=status.HTTP_201_CREATED)


class SupportTicketDetailView(generics.GenericAPIView):
    def get(self, request, pk):
        ticket = _tickets(request.user).filter(pk=pk).first()
        if ticket is None:
            return response.Response({'detail': 'Chat not found.'}, status=status.HTTP_404_NOT_FOUND)
        SupportService.mark_read(ticket, by_admin=False)
        return response.Response(SupportTicketDetailSerializer(ticket).data)


class SupportMessageCreateView(generics.GenericAPIView):
    def post(self, request, pk):
        ticket = _tickets(request.user).filter(pk=pk).first()
        if ticket is None:
            return response.Response({'detail': 'Chat not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            message = SupportService.post(
                ticket,
                sender=SupportMessage.Sender.CUSTOMER,
                body=str(request.data.get('body', ''))[:2000],
                author=request.user,
            )
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(SupportMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class SupportUnreadView(generics.GenericAPIView):
    def get(self, request):
        count = (
            SupportMessage.objects.filter(ticket__user=request.user, sender=SupportMessage.Sender.SUPPORT)
            .filter(Q(ticket__customer_read_at__isnull=True) | Q(created_at__gt=F('ticket__customer_read_at')))
            .aggregate(n=Count('id'))['n']
        )
        return response.Response({'count': count})


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
