from rest_framework import generics, response, status

from apps.bookings.models import Booking, BookingAssignment

from .assignment_service import AssignmentService
from .permissions import IsPartner
from .serializers import (
    PartnerAvailabilitySerializer,
    PartnerJobRejectSerializer,
    PartnerJobSerializer,
    PartnerProfileSerializer,
)


class PartnerMeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsPartner]
    serializer_class = PartnerProfileSerializer

    def get_object(self):
        return self.request.user.partner_profile

    def get_serializer_class(self):
        if self.request.method in {'PUT', 'PATCH'}:
            return PartnerAvailabilitySerializer
        return PartnerProfileSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return response.Response(PartnerProfileSerializer(instance).data)


class PartnerJobListView(generics.ListAPIView):
    permission_classes = [IsPartner]
    serializer_class = PartnerJobSerializer

    def get_queryset(self):
        partner = self.request.user.partner_profile
        assignment_status = self.request.query_params.get('status', BookingAssignment.Status.PENDING)
        booking_ids = BookingAssignment.objects.filter(
            partner=partner,
            status=assignment_status,
        ).values_list('booking_id', flat=True)
        return (
            Booking.objects.filter(id__in=booking_ids, status=Booking.Status.CONFIRMED)
            .select_related('customer', 'address', 'city')
            .prefetch_related('items', 'assignments', 'payments')
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['partner'] = self.request.user.partner_profile
        assignments = {
            a.booking_id: a
            for a in BookingAssignment.objects.filter(
                partner=self.request.user.partner_profile,
                status=self.request.query_params.get('status', BookingAssignment.Status.PENDING),
            )
        }
        context['assignments_map'] = assignments
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        assignments_map = self.get_serializer_context()['assignments_map']
        partner = request.user.partner_profile
        data = []
        for booking in queryset:
            assignment = assignments_map.get(booking.id)
            serializer = PartnerJobSerializer(
                booking,
                context={'request': request, 'partner': partner, 'assignment': assignment},
            )
            data.append(serializer.data)
        return response.Response(data)


class PartnerJobDetailView(generics.RetrieveAPIView):
    permission_classes = [IsPartner]
    serializer_class = PartnerJobSerializer

    def get_queryset(self):
        partner = self.request.user.partner_profile
        booking_ids = BookingAssignment.objects.filter(partner=partner).values_list('booking_id', flat=True)
        return (
            Booking.objects.filter(id__in=booking_ids)
            .select_related('customer', 'address', 'city')
            .prefetch_related('items', 'assignments', 'payments')
        )

    def retrieve(self, request, *args, **kwargs):
        booking = self.get_object()
        partner = request.user.partner_profile
        assignment = booking.assignments.filter(partner=partner).order_by('-assigned_at').first()
        serializer = self.get_serializer(
            booking,
            context={'request': request, 'partner': partner, 'assignment': assignment},
        )
        return response.Response(serializer.data)


class PartnerJobAcceptView(generics.GenericAPIView):
    permission_classes = [IsPartner]

    def post(self, request, pk):
        partner = request.user.partner_profile
        assignment = BookingAssignment.objects.filter(
            pk=pk,
            partner=partner,
            status=BookingAssignment.Status.PENDING,
        ).first()
        if assignment is None:
            return response.Response({'detail': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)

        AssignmentService.accept_assignment(partner=partner, assignment_id=str(assignment.id))
        booking = assignment.booking
        serializer = PartnerJobSerializer(
            booking,
            context={'request': request, 'partner': partner, 'assignment': assignment},
        )
        return response.Response(serializer.data)


class PartnerJobRejectView(generics.GenericAPIView):
    permission_classes = [IsPartner]
    serializer_class = PartnerJobRejectSerializer

    def post(self, request, pk):
        partner = request.user.partner_profile
        assignment = BookingAssignment.objects.filter(
            pk=pk,
            partner=partner,
            status=BookingAssignment.Status.PENDING,
        ).first()
        if assignment is None:
            return response.Response({'detail': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AssignmentService.reject_assignment(
            partner=partner,
            assignment_id=str(assignment.id),
            reason=serializer.validated_data.get('reason', ''),
        )
        return response.Response({'detail': 'Job rejected. Reassignment attempted if another partner is available.'})
