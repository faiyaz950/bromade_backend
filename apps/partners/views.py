import json
from datetime import timedelta

from django.db import IntegrityError
from django.db.models import Sum
from django.utils import timezone
from rest_framework import generics, permissions, response, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.bookings.models import Booking, BookingAssignment
from apps.bookings.reviews import rating_summary, ratings_for_partner
from apps.payments.models import Payment

from .assignment_service import AssignmentService
from .models import PartnerProfile
from .wallet_service import InsufficientWalletError
from .permissions import IsApprovedPartner
from .serializers import (
    PartnerAvailabilitySerializer,
    PartnerDeviceTokenSerializer,
    PartnerJobRejectSerializer,
    PartnerJobSerializer,
    PartnerProfileSerializer,
    PartnerRegistrationSerializer,
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


class PartnerRegisterView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PartnerRegistrationSerializer

    def put(self, request):
        profile = ensure_partner_profile(request.user)
        serializer = self.get_serializer(data=request.data, context={'partner': profile, 'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        profile.refresh_from_db()
        return response.Response(PartnerProfileSerializer(profile).data)


class PartnerCatalogView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.catalog.models import Service
        from apps.locations.models import City

        cities = [
            {'id': str(city.id), 'name': city.name, 'state': city.state}
            for city in City.objects.filter(is_active=True).order_by('name')
        ]
        services = [
            {'id': str(service.id), 'name': service.name, 'category': service.category.name}
            for service in Service.objects.filter(is_active=True).select_related('category').order_by(
                'category__name', 'name'
            )
        ]
        return response.Response({'cities': cities, 'services': services})


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

        assigned_today = Booking.objects.filter(
            assignments__partner=partner,
            assignments__status=BookingAssignment.Status.ACCEPTED,
            scheduled_date=today,
        ).exclude(status=Booking.Status.CANCELLED).distinct()
        last_7 = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            day_qs = completed.filter(scheduled_date=day)
            last_7.append({'date': day.isoformat(), 'amount': _sum(day_qs), 'count': _count(day_qs)})

        return response.Response(
            {
                'today_jobs': _count(assigned_today),
                'today_pending': _count(assigned_today.exclude(status=Booking.Status.COMPLETED)),
                'last_7_days': last_7,
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
                .prefetch_related('items', 'assignments', 'payments', 'rating', 'status_logs')
            )

        assignment_status = requested
        booking_ids = BookingAssignment.objects.filter(
            partner=partner,
            status=assignment_status,
        ).values_list('booking_id', flat=True)
        queryset = Booking.objects.filter(id__in=booking_ids).select_related(
            'customer', 'address', 'city'
        ).prefetch_related('items', 'assignments', 'payments', 'rating', 'status_logs')
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
            .prefetch_related('items', 'assignments', 'payments', 'rating', 'status_logs')
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

        try:
            AssignmentService.accept_assignment(partner=partner, assignment_id=str(assignment.id))
        except InsufficientWalletError as exc:
            return response.Response(
                {
                    'detail': str(exc),
                    'code': 'low_wallet_balance',
                    'wallet_balance': str(exc.wallet_balance),
                    'required_amount': str(exc.required_amount),
                    'shortfall': str(exc.shortfall),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
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
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, pk):
        # A multipart body (sent whenever a photo is attached) carries the
        # checklist as a JSON-encoded string field, not a nested list. DRF's
        # ListField reads QueryDict values via getlist(), so the parsed list
        # must be assigned with setlist() — plain item assignment wraps it
        # in an extra list layer and fails validation.
        data = request.data
        checklist_raw = data.get('checklist')
        if isinstance(checklist_raw, str):
            try:
                parsed_checklist = json.loads(checklist_raw)
            except (TypeError, ValueError):
                parsed_checklist = None
            if isinstance(parsed_checklist, list):
                data = data.copy()
                data.setlist('checklist', parsed_checklist)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            if serializer.validated_data['visit_status'] == Booking.VisitStatus.COMPLETED:
                booking = VisitService.complete(
                    partner=request.user.partner_profile,
                    assignment_id=str(pk),
                    checklist=serializer.validated_data.get('checklist'),
                    photo=serializer.validated_data.get('photo'),
                )
            else:
                booking = VisitService.advance(
                    partner=request.user.partner_profile,
                    assignment_id=str(pk),
                    visit_status=serializer.validated_data['visit_status'],
                    photo=serializer.validated_data.get('photo'),
                    start_code=serializer.validated_data.get('start_code', ''),
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
            )
            assignment = BookingAssignment.objects.select_related('booking').get(
                pk=pk, partner=request.user.partner_profile
            )
        except BookingAssignment.DoesNotExist:
            return response.Response({'detail': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(_job_payload(request, assignment.booking, assignment))


class PartnerLocationView(generics.GenericAPIView):
    permission_classes = [IsApprovedPartner]

    def post(self, request, pk):
        try:
            latitude = float(request.data.get('latitude'))
            longitude = float(request.data.get('longitude'))
        except (TypeError, ValueError):
            return response.Response({'detail': 'Send latitude and longitude.'}, status=status.HTTP_400_BAD_REQUEST)
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return response.Response({'detail': 'Invalid coordinates.'}, status=status.HTTP_400_BAD_REQUEST)
        assignment = (
            BookingAssignment.objects.select_related('booking')
            .filter(pk=pk, partner=request.user.partner_profile, status=BookingAssignment.Status.ACCEPTED)
            .first()
        )
        if assignment is None:
            return response.Response({'detail': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            VisitService.update_location(assignment, latitude, longitude)
        except ValueError as exc:
            return response.Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return response.Response({'ok': True})


def _rating_tips(summary):
    tips = []
    average = summary['average']
    if summary['count'] == 0:
        return [
            'Finish your first few jobs on time to build your rating.',
            'Greet the customer, explain the work and show the result before leaving.',
        ]
    if average < 4.5:
        tips.append('Call the customer when you start travelling so they know when to expect you.')
    if summary['distribution'].get('1', 0) + summary['distribution'].get('2', 0) > 0:
        tips.append('Low ratings usually come from delays or unclear pricing. Confirm the work before starting.')
    tips.append('Take clear before and after photos. Customers trust jobs they can see.')
    tips.append('Clean up the work area and ask the customer to check everything before you complete the job.')
    if average >= 4.8:
        tips.insert(0, 'Excellent work! Keep it up to get more job requests.')
    return tips


class PartnerRatingsView(generics.GenericAPIView):
    permission_classes = [IsApprovedPartner]

    def get(self, request):
        summary = rating_summary(ratings_for_partner(request.user.partner_profile), request=request)
        summary['tips'] = _rating_tips(summary)
        return response.Response(summary)
