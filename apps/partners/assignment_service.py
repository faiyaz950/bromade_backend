from __future__ import annotations

from typing import Optional

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.bookings.models import Booking, BookingAssignment, BookingStatusLog

MAX_JOB_OFFERS = 25


class AssignmentService:
    @staticmethod
    def _eligible_partners(booking: Booking):
        from apps.partners.models import PartnerProfile

        package = booking.items.select_related('package__service').first()
        if package is None:
            return PartnerProfile.objects.none()

        service = package.package.service
        rejected_ids = BookingAssignment.objects.filter(
            booking=booking,
            status=BookingAssignment.Status.REJECTED,
        ).values_list('partner_id', flat=True)

        from apps.partners.models import PartnerProfile

        return (
            PartnerProfile.objects.filter(
                is_active=True,
                approval_status=PartnerProfile.ApprovalStatus.APPROVED,
                is_available_for_assignment=True,
                cities__city=booking.city,
                services__service=service,
            )
            .exclude(id__in=rejected_ids)
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
        )

    @staticmethod
    def auto_assign_booking(booking: Booking) -> Optional[BookingAssignment]:
        if booking.status != Booking.Status.CONFIRMED:
            return None

        accepted = BookingAssignment.objects.filter(
            booking=booking,
            status=BookingAssignment.Status.ACCEPTED,
        ).first()
        if accepted is not None:
            return accepted

        from apps.partners.notifications import notify_partner_new_job

        eligible = list(AssignmentService._eligible_partners(booking)[:MAX_JOB_OFFERS])
        offered = None
        new_names = []
        for partner in eligible:
            pending = BookingAssignment.objects.filter(
                booking=booking,
                partner=partner,
                status=BookingAssignment.Status.PENDING,
            ).first()
            if pending is not None:
                offered = offered or pending
                continue
            assignment = BookingAssignment.objects.create(
                booking=booking,
                partner=partner,
                status=BookingAssignment.Status.PENDING,
            )
            notify_partner_new_job(partner, booking)
            new_names.append(partner.full_name)
            offered = offered or assignment

        if offered is None:
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

        previous = booking.assignment_status
        if previous != Booking.AssignmentStatus.PENDING or new_names:
            booking.assignment_status = Booking.AssignmentStatus.PENDING
            booking.save(update_fields=['assignment_status', 'updated_at'])
            if new_names:
                BookingStatusLog.objects.create(
                    booking=booking,
                    from_status=previous,
                    to_status=Booking.AssignmentStatus.PENDING,
                    note=f'Offered to {", ".join(new_names)}.',
                )
        return offered

    @staticmethod
    def accept_assignment(*, partner, assignment_id: str) -> BookingAssignment:
        from apps.partners.wallet_service import WalletService

        with transaction.atomic():
            assignment = BookingAssignment.objects.select_related('booking').select_for_update().get(
                pk=assignment_id,
                partner=partner,
                status=BookingAssignment.Status.PENDING,
            )
            booking = assignment.booking
            WalletService.debit_commission(partner=partner, booking=booking)
            now = timezone.now()
            assignment.status = BookingAssignment.Status.ACCEPTED
            assignment.responded_at = now
            assignment.save(update_fields=['status', 'responded_at', 'updated_at'])
            BookingAssignment.objects.filter(
                booking=booking,
                status=BookingAssignment.Status.PENDING,
            ).exclude(pk=assignment.pk).update(
                status=BookingAssignment.Status.REASSIGNED,
                responded_at=now,
                rejection_reason='Another partner accepted this job.',
                updated_at=now,
            )

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

        remaining = BookingAssignment.objects.filter(
            booking=booking,
            status=BookingAssignment.Status.PENDING,
        ).first()
        previous = booking.assignment_status
        if remaining is not None:
            booking.assignment_status = Booking.AssignmentStatus.PENDING
            booking.save(update_fields=['assignment_status', 'updated_at'])
            BookingStatusLog.objects.create(
                booking=booking,
                from_status=previous,
                to_status=Booking.AssignmentStatus.PENDING,
                note=f'Rejected by partner {partner.full_name}. Still offered to others.',
            )
            return remaining

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
                Booking.AssignmentStatus.PENDING,
            ],
        )
        for booking in bookings:
            if AssignmentService.auto_assign_booking(booking) is not None:
                assigned += 1
        return assigned
