from rest_framework import generics, response, status

from .models import Booking, BookingRating
from .serializers import (
    BookingDraftSerializer,
    BookingPriceSummarySerializer,
    BookingRatingSerializer,
    BookingSerializer,
)
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
        return (
            Booking.objects.filter(customer=self.request.user)
            .prefetch_related('items', 'payments', 'assignments__partner')
            .select_related('rating')
        )


class BookingDetailView(generics.RetrieveAPIView):
    serializer_class = BookingSerializer

    def get_queryset(self):
        return (
            Booking.objects.filter(customer=self.request.user)
            .prefetch_related('items', 'payments', 'assignments__partner')
            .select_related('rating')
        )


class BookingConfirmView(generics.GenericAPIView):
    """Mark a pending booking as confirmed after successful payment orchestration."""

    def post(self, request, pk):
        booking = (
            Booking.objects.filter(customer=request.user, pk=pk)
            .prefetch_related('items', 'payments', 'assignments__partner')
            .select_related('rating')
            .first()
        )
        if booking is None:
            return response.Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if booking.status not in {Booking.Status.DRAFT, Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED}:
            return response.Response({'detail': 'Booking cannot be confirmed.'}, status=status.HTTP_400_BAD_REQUEST)

        if booking.status != Booking.Status.CONFIRMED:
            booking.start_visit_tracking(note='Booking confirmed.')
        return response.Response(BookingSerializer(booking).data)


class BookingRateView(generics.GenericAPIView):
    serializer_class = BookingRatingSerializer

    def post(self, request, pk):
        booking = Booking.objects.filter(customer=request.user, pk=pk).first()
        if booking is None:
            return response.Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if booking.status != Booking.Status.COMPLETED:
            return response.Response(
                {'detail': 'You can rate after the visit is completed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if BookingRating.objects.filter(booking=booking).exists():
            return response.Response({'detail': 'This booking is already rated.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        BookingRating.objects.create(
            booking=booking,
            stars=serializer.validated_data['stars'],
            comment=serializer.validated_data.get('comment', ''),
        )
        booking = (
            Booking.objects.filter(pk=booking.pk)
            .prefetch_related('items', 'payments', 'assignments__partner')
            .select_related('rating')
            .get()
        )
        return response.Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)
