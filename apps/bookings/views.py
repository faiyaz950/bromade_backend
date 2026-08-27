from rest_framework import generics, response, status

from .models import Booking, BookingStatusLog
from .serializers import BookingDraftSerializer, BookingPriceSummarySerializer, BookingSerializer
from .services import BookingService


class BookingPriceSummaryView(generics.GenericAPIView):
    serializer_class = BookingPriceSummarySerializer

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return response.Response(serializer.data)


class BookingCreateView(generics.GenericAPIView):
    serializer_class = BookingDraftSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = BookingService.create_booking(user=request.user, **serializer.validated_data)
        except ValueError as exc:
            return response.Response({'coupon_code': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class BookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer

    def get_queryset(self):
        return Booking.objects.filter(customer=self.request.user).prefetch_related('items', 'payments')


class BookingDetailView(generics.RetrieveAPIView):
    serializer_class = BookingSerializer

    def get_queryset(self):
        return Booking.objects.filter(customer=self.request.user).prefetch_related('items', 'payments')


class BookingConfirmView(generics.GenericAPIView):
    """Mark a pending booking as confirmed after successful payment orchestration."""

    def post(self, request, pk):
        booking = Booking.objects.filter(customer=request.user, pk=pk).prefetch_related('items').first()
        if booking is None:
            return response.Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if booking.status not in {Booking.Status.DRAFT, Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED}:
            return response.Response({'detail': 'Booking cannot be confirmed.'}, status=status.HTTP_400_BAD_REQUEST)

        previous_status = booking.status
        if booking.status != Booking.Status.CONFIRMED:
            booking.status = Booking.Status.CONFIRMED
            booking.save(update_fields=['status', 'updated_at'])
            BookingStatusLog.objects.create(
                booking=booking,
                from_status=previous_status,
                to_status=Booking.Status.CONFIRMED,
                note='Booking confirmed.',
            )
        return response.Response(BookingSerializer(booking).data)
