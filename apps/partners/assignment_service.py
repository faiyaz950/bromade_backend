from __future__ import annotations

from typing import Optional

from django.db.models import Count, Q
from django.utils import timezone

from apps.bookings.models import Booking, BookingAssignment, BookingStatusLog


class AssignmentService:
    @staticmethod
    def auto_assign_booking(booking: Booking) -> Optional[BookingAssignment]:
        if booking.status != Booking.Status.CONFIRMED:
            return None

        open_assignment = (
            BookingAssignment.objects.filter(
                booking=booking,
                status__in=[
                    BookingAssignment.Status.PENDING,
                    BookingAssignment.Status.ACCEPTED,
                ],
            )
            .order_by('-assigned_at')
            .first()
        )
        if open_assignment is not None:
            return open_assignment

        package = booking.items.select_related('package__service').first()
        if package is None:
            return None

        service = package.package.service
        excluded_partner_ids = BookingAssignment.objects.filter(booking=booking).values_list('partner_id', flat=True)

        from apps.partners.models import PartnerProfile

        eligible = (
            PartnerProfile.objects.filter(
                is_active=True,
                approval_status=PartnerProfile.ApprovalStatus.APPROVED,
                is_available_for_assignment=True,
                cities__city=booking.city,
                services__service=service,
            )
            .exclude(id__in=excluded_partner_ids)
            .exclude(unavailable_dates__date=booking.scheduled_date)
            .annotate(
                active_jobs=Count(
                    'assignments',
                    filter=Q(
                        assignments__status__in=[
                            BookingAssignment.Status.PENDING,
                            BookingAssignment.Status.ACCEPTED,
                        ],
                        assignments__booking__scheduled_date=booking.scheduled_date,
                    ),
                )
            )
            .order_by('active_jobs', 'created_at')
            .distinct()
            .first()
        )

        if eligible is None:
            previous = booking.assignment_status
            booking.assignment_status = Booking.AssignmentStatus.UNASSIGNED
            booking.save(update_fields=['assignment_status', 'updated_at'])
            if previous != Booking.AssignmentStatus.UNASSIGNED:
                BookingStatusLog.objects.create(
                    booking=booking,
                    from_status=previous,
                    to_status=Booking.AssignmentStatus.UNASSIGNED,
                    note='No eligible partner available for auto-assignment.',
                )
            return None

        assignment = BookingAssignment.objects.create(
            booking=booking,
            partner=eligible,
            status=BookingAssignment.Status.PENDING,
        )
        previous = booking.assignment_status
        booking.assignment_status = Booking.AssignmentStatus.PENDING
        booking.save(update_fields=['assignment_status', 'updated_at'])
        BookingStatusLog.objects.create(
            booking=booking,
            from_status=previous,
            to_status=Booking.AssignmentStatus.PENDING,
            note=f'Assigned to partner {eligible.full_name}.',
        )
        from apps.partners.notifications import notify_partner_new_job

        notify_partner_new_job(eligible, booking)
        return assignment

    @staticmethod
    def accept_assignment(*, partner, assignment_id: str) -> BookingAssignment:
        assignment = BookingAssignment.objects.select_related('booking').get(
            pk=assignment_id,
            partner=partner,
            status=BookingAssignment.Status.PENDING,
        )
        booking = assignment.booking
        assignment.status = BookingAssignment.Status.ACCEPTED
        assignment.responded_at = timezone.now()
        assignment.save(update_fields=['status', 'responded_at', 'updated_at'])

        previous = booking.assignment_status
        booking.assignment_status = Booking.AssignmentStatus.ACCEPTED
        booking.save(update_fields=['assignment_status', 'updated_at'])
        BookingStatusLog.objects.create(
            booking=booking,
            from_status=previous,
            to_status=Booking.AssignmentStatus.ACCEPTED,
            note=f'Accepted by partner {partner.full_name}.',
        )
        return assignment

    @staticmethod
    def reject_assignment(*, partner, assignment_id: str, reason: str = '') -> Optional[BookingAssignment]:
        assignment = BookingAssignment.objects.select_related('booking').get(
            pk=assignment_id,
            partner=partner,
            status=BookingAssignment.Status.PENDING,
        )
        booking = assignment.booking
        assignment.status = BookingAssignment.Status.REJECTED
        assignment.rejection_reason = reason[:255]
        assignment.responded_at = timezone.now()
        assignment.save(update_fields=['status', 'rejection_reason', 'responded_at', 'updated_at'])

        previous = booking.assignment_status
        booking.assignment_status = Booking.AssignmentStatus.REJECTED
        booking.save(update_fields=['assignment_status', 'updated_at'])
        BookingStatusLog.objects.create(
            booking=booking,
            from_status=previous,
            to_status=Booking.AssignmentStatus.REJECTED,
            note=f'Rejected by partner {partner.full_name}.',
        )
        return AssignmentService.auto_assign_booking(booking)

    @staticmethod
    def assign_open_confirmed_bookings() -> int:
        assigned = 0
        bookings = Booking.objects.filter(
            status=Booking.Status.CONFIRMED,
            assignment_status__in=[
                Booking.AssignmentStatus.UNASSIGNED,
                Booking.AssignmentStatus.REJECTED,
            ],
        )
        for booking in bookings:
            if AssignmentService.auto_assign_booking(booking) is not None:
                assigned += 1
        return assigned
