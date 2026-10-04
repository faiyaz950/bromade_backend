from rest_framework import generics, response, status

from .models import Booking, BookingRating
from .serializers import (
    BookingCancelSerializer,
    BookingDraftSerializer,
    BookingPriceSummarySerializer,
    BookingRatingSerializer,
    BookingRescheduleSerializer,
    BookingSerializer,
)
from .services import BookingService

BOOKING_PREFETCH = ('items__package__service__category', 'payments', 'assignments__partner__user', 'status_logs')
BOOKING_RELATED = ('rating', 'address', 'city')


def _customer_bookings(user):
    return Booking.objects.filter(customer=user).prefetch_related(*BOOKING_PREFETCH).select_related(*BOOKING_RELATED)


def _booking_response(request, booking_id, status_code=status.HTTP_200_OK):
    booking = Booking.objects.prefetch_related(*BOOKING_PREFETCH).select_related(*BOOKING_RELATED).get(pk=booking_id)
    return response.Response(BookingSerializer(booking, context={'request': request}).data, status=status_code)


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
        return _booking_response(request, booking.pk, status.HTTP_201_CREATED)


class BookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer

    def get_queryset(self):
        return _customer_bookings(self.request.user)


class BookingDetailView(generics.RetrieveAPIView):
    serializer_class = BookingSerializer

    def get_queryset(self):
        return _customer_bookings(self.request.user)


class BookingConfirmView(generics.GenericAPIView):
    """Mark a pending booking as confirmed after successful payment orchestration."""

    def post(self, request, pk):
        booking = Booking.objects.filter(customer=request.user, pk=pk).first()
        if booking is None:
            return response.Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if booking.status not in {Booking.Status.DRAFT, Booking.Status.PENDING_PAYMENT, Booking.Status.CONFIRMED}:
            return response.Response({'detail': 'Booking cannot be confirmed.'}, status=status.HTTP_400_BAD_REQUEST)

        if booking.status != Booking.Status.CONFIRMED:
            booking.start_visit_tracking(note='Booking confirmed.')
        from apps.partners.assignment_service import AssignmentService

        AssignmentService.auto_assign_booking(booking)
        return _booking_response(request, booking.pk)


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
        return _booking_response(request, booking.pk, status.HTTP_201_CREATED)


class BookingCancelView(generics.GenericAPIView):
    serializer_class = BookingCancelSerializer

    def post(self, request, pk):
        booking = Booking.objects.filter(customer=request.user, pk=pk).first()
        if booking is None:
            return response.Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            BookingService.cancel_booking(booking=booking, reason=serializer.validated_data.get('reason', ''))
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _booking_response(request, booking.pk)


class BookingRescheduleView(generics.GenericAPIView):
    serializer_class = BookingRescheduleSerializer

    def post(self, request, pk):
        booking = Booking.objects.filter(customer=request.user, pk=pk).first()
        if booking is None:
            return response.Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            BookingService.reschedule_booking(booking=booking, **serializer.validated_data)
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _booking_response(request, booking.pk)
