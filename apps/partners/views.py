from datetime import timedelta

from django.db import IntegrityError
from django.db.models import Sum
from django.utils import timezone
from rest_framework import generics, permissions, response, status

from apps.bookings.models import Booking, BookingAssignment
from apps.payments.models import Payment

from .assignment_service import AssignmentService
from .models import PartnerProfile
from .permissions import IsApprovedPartner
from .serializers import (
    PartnerAvailabilitySerializer,
    PartnerDeviceTokenSerializer,
    PartnerJobRejectSerializer,
    PartnerJobSerializer,
    PartnerProfileSerializer,
    PartnerUnavailableDateSerializer,
    PartnerVisitActionSerializer,
)
from .visit_service import VisitService


def ensure_partner_profile(user):
    existing = getattr(user, 'partner_profile', None)
    if existing is not None:
        return existing
    full_name = f'{user.first_name} {user.last_name}'.strip() or (user.phone_number or 'Partner')
    try:
        return PartnerProfile.objects.create(
            user=user,
            full_name=full_name,
            is_active=False,
            approval_status=PartnerProfile.ApprovalStatus.PENDING,
        )
    except IntegrityError:
        return PartnerProfile.objects.get(user=user)


def _job_payload(request, booking, assignment=None):
    partner = request.user.partner_profile
    if assignment is None:
        assignment = booking.assignments.filter(partner=partner).order_by('-assigned_at').first()
    return PartnerJobSerializer(
        booking,
        context={'request': request, 'partner': partner, 'assignment': assignment},
    ).data


class PartnerMeView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PartnerProfileSerializer

    def get_object(self):
        return ensure_partner_profile(self.request.user)

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


class PartnerDeviceTokenView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PartnerDeviceTokenSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = ensure_partner_profile(request.user)
        token, _created = profile.device_tokens.update_or_create(
            token=serializer.validated_data['token'],
            defaults={'platform': serializer.validated_data.get('platform', 'android')},
        )
        return response.Response(PartnerDeviceTokenSerializer(token).data, status=status.HTTP_201_CREATED)


class PartnerUnavailableDateListView(generics.ListCreateAPIView):
    permission_classes = [IsApprovedPartner]
    serializer_class = PartnerUnavailableDateSerializer

    def get_queryset(self):
        return self.request.user.partner_profile.unavailable_dates.filter(
            date__gte=timezone.localdate() - timedelta(days=1)
        )

    def perform_create(self, serializer):
        serializer.save(partner=self.request.user.partner_profile)


class PartnerUnavailableDateDeleteView(generics.DestroyAPIView):
    permission_classes = [IsApprovedPartner]
    serializer_class = PartnerUnavailableDateSerializer

    def get_queryset(self):
        return self.request.user.partner_profile.unavailable_dates.all()


class PartnerEarningsView(generics.GenericAPIView):
    permission_classes = [IsApprovedPartner]

    def get(self, request):
        partner = request.user.partner_profile
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        completed = Booking.objects.filter(
            assignments__partner=partner,
            assignments__status=BookingAssignment.Status.ACCEPTED,
            status=Booking.Status.COMPLETED,
        ).distinct()

        def _sum(qs):
            return qs.aggregate(total=Sum('total_amount'))['total'] or 0

        def _count(qs):
            return qs.count()

        cash_paid = completed.filter(
            payments__method=Payment.Method.CASH,
            payments__status=Payment.Status.PAID,
        ).distinct()
        online_paid = completed.filter(
            payments__method=Payment.Method.ONLINE,
            payments__status=Payment.Status.PAID,
        ).distinct()

        return response.Response(
            {
                'today_amount': _sum(completed.filter(scheduled_date=today)),
                'today_count': _count(completed.filter(scheduled_date=today)),
                'week_amount': _sum(completed.filter(scheduled_date__gte=week_start)),
                'week_count': _count(completed.filter(scheduled_date__gte=week_start)),
                'month_amount': _sum(completed.filter(scheduled_date__gte=month_start)),
                'month_count': _count(completed.filter(scheduled_date__gte=month_start)),
                'completed_amount': _sum(completed),
                'completed_count': _count(completed),
                'cash_collected': _sum(cash_paid),
                'online_collected': _sum(online_paid),
            }
        )


class PartnerJobListView(generics.ListAPIView):
    permission_classes = [IsApprovedPartner]
    serializer_class = PartnerJobSerializer

    def _requested_status(self):
        return self.request.query_params.get('status', BookingAssignment.Status.PENDING)

    def get_queryset(self):
        partner = self.request.user.partner_profile
        requested = self._requested_status()
        if requested == 'completed':
            booking_ids = BookingAssignment.objects.filter(
                partner=partner,
                status=BookingAssignment.Status.ACCEPTED,
            ).values_list('booking_id', flat=True)
            return (
                Booking.objects.filter(id__in=booking_ids, status=Booking.Status.COMPLETED)
                .select_related('customer', 'address', 'city')
                .prefetch_related('items', 'assignments', 'payments', 'rating')
            )

        assignment_status = requested
        booking_ids = BookingAssignment.objects.filter(
            partner=partner,
            status=assignment_status,
        ).values_list('booking_id', flat=True)
        queryset = Booking.objects.filter(id__in=booking_ids).select_related(
            'customer', 'address', 'city'
        ).prefetch_related('items', 'assignments', 'payments', 'rating')
        if assignment_status in {
            BookingAssignment.Status.PENDING,
            BookingAssignment.Status.ACCEPTED,
        }:
            queryset = queryset.filter(status=Booking.Status.CONFIRMED)
        return queryset.order_by('scheduled_date', 'scheduled_time')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['partner'] = self.request.user.partner_profile
        requested = self._requested_status()
        assignment_status = (
            BookingAssignment.Status.ACCEPTED if requested == 'completed' else requested
        )
        assignments = {
            a.booking_id: a
            for a in BookingAssignment.objects.filter(
                partner=self.request.user.partner_profile,
                status=assignment_status,
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
    permission_classes = [IsApprovedPartner]
    serializer_class = PartnerJobSerializer

    def get_queryset(self):
        partner = self.request.user.partner_profile
        booking_ids = BookingAssignment.objects.filter(partner=partner).values_list('booking_id', flat=True)
        return (
            Booking.objects.filter(id__in=booking_ids)
            .select_related('customer', 'address', 'city')
            .prefetch_related('items', 'assignments', 'payments', 'rating')
        )

    def retrieve(self, request, *args, **kwargs):
        booking = self.get_object()
        return response.Response(_job_payload(request, booking))


class PartnerJobAcceptView(generics.GenericAPIView):
    permission_classes = [IsApprovedPartner]

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
        assignment.refresh_from_db()
        return response.Response(_job_payload(request, assignment.booking, assignment))


class PartnerJobRejectView(generics.GenericAPIView):
    permission_classes = [IsApprovedPartner]
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


class PartnerVisitAdvanceView(generics.GenericAPIView):
    permission_classes = [IsApprovedPartner]
    serializer_class = PartnerVisitActionSerializer

    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            if serializer.validated_data['visit_status'] == Booking.VisitStatus.COMPLETED:
                booking = VisitService.complete(
                    partner=request.user.partner_profile,
                    assignment_id=str(pk),
                    checklist=serializer.validated_data.get('checklist'),
                )
            else:
                booking = VisitService.advance(
                    partner=request.user.partner_profile,
                    assignment_id=str(pk),
                    visit_status=serializer.validated_data['visit_status'],
                )
        except BookingAssignment.DoesNotExist:
            return response.Response({'detail': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(_job_payload(request, booking))


class PartnerCashCollectView(generics.GenericAPIView):
    permission_classes = [IsApprovedPartner]

    def post(self, request, pk):
        try:
            VisitService.collect_cash(
                partner=request.user.partner_profile,
                assignment_id=str(pk),
                required=True,
            )
            assignment = BookingAssignment.objects.select_related('booking').get(
                pk=pk, partner=request.user.partner_profile
            )
        except BookingAssignment.DoesNotExist:
            return response.Response({'detail': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(_job_payload(request, assignment.booking, assignment))
