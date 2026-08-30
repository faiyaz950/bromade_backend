from __future__ import annotations

from django.utils import timezone

from apps.bookings.models import Booking, BookingAssignment, BookingStatusLog, default_visit_checklist
from apps.payments.models import Payment


VISIT_FLOW = [
    Booking.VisitStatus.SCHEDULED,
    Booking.VisitStatus.ON_THE_WAY,
    Booking.VisitStatus.ARRIVED,
    Booking.VisitStatus.IN_PROGRESS,
    Booking.VisitStatus.COMPLETED,
]


class VisitService:
    @staticmethod
    def _accepted_assignment(*, partner, assignment_id: str) -> BookingAssignment:
        return BookingAssignment.objects.select_related('booking').get(
            pk=assignment_id,
            partner=partner,
            status=BookingAssignment.Status.ACCEPTED,
        )

    @staticmethod
    def _require_open_visit(booking: Booking) -> None:
        if booking.status == Booking.Status.CANCELLED:
            raise ValueError('This booking was cancelled.')
        if booking.status == Booking.Status.COMPLETED:
            raise ValueError('This visit is already completed.')
        if booking.status != Booking.Status.CONFIRMED:
            raise ValueError('This visit is not ready to start.')

    @classmethod
    def advance(cls, *, partner, assignment_id: str, visit_status: str) -> Booking:
        if visit_status not in VISIT_FLOW:
            raise ValueError('Unknown visit status.')
        assignment = cls._accepted_assignment(partner=partner, assignment_id=assignment_id)
        booking = assignment.booking
        cls._require_open_visit(booking)

        current = booking.visit_status or Booking.VisitStatus.SCHEDULED
        if current not in VISIT_FLOW:
            current = Booking.VisitStatus.SCHEDULED
        current_index = VISIT_FLOW.index(current)
        next_index = VISIT_FLOW.index(visit_status)
        if next_index != current_index + 1:
            raise ValueError('Advance the visit one step at a time.')
        if visit_status == Booking.VisitStatus.COMPLETED:
            return cls.complete(partner=partner, assignment_id=assignment_id)

        previous = booking.visit_status
        booking.visit_status = visit_status
        booking.save(update_fields=['visit_status', 'updated_at'])
        BookingStatusLog.objects.create(
            booking=booking,
            from_status=previous,
            to_status=visit_status,
            note=f'Visit updated by {partner.full_name}.',
        )
        return booking

    @classmethod
    def complete(cls, *, partner, assignment_id: str, checklist=None) -> Booking:
        assignment = cls._accepted_assignment(partner=partner, assignment_id=assignment_id)
        booking = assignment.booking
        cls._require_open_visit(booking)
        if booking.visit_status != Booking.VisitStatus.IN_PROGRESS:
            raise ValueError('Start the service before marking it complete.')

        items = checklist if isinstance(checklist, list) and checklist else booking.checklist
        if not items:
            items = default_visit_checklist()
        for item in items:
            item['done'] = True

        previous_visit = booking.visit_status
        previous_status = booking.status
        booking.checklist = items
        booking.visit_status = Booking.VisitStatus.COMPLETED
        booking.status = Booking.Status.COMPLETED
        booking.save(update_fields=['checklist', 'visit_status', 'status', 'updated_at'])
        BookingStatusLog.objects.create(
            booking=booking,
            from_status=previous_visit,
            to_status=Booking.VisitStatus.COMPLETED,
            note=f'Visit completed by {partner.full_name}.',
        )
        if previous_status != Booking.Status.COMPLETED:
            BookingStatusLog.objects.create(
                booking=booking,
                from_status=previous_status,
                to_status=Booking.Status.COMPLETED,
                note='Booking completed.',
            )
        cls.collect_cash(partner=partner, assignment_id=assignment_id, required=False)
        return booking

    @classmethod
    def collect_cash(cls, *, partner, assignment_id: str, required: bool = True) -> Payment | None:
        assignment = cls._accepted_assignment(partner=partner, assignment_id=assignment_id)
        booking = assignment.booking
        payment = booking.payments.filter(method=Payment.Method.CASH).order_by('-created_at').first()
        if payment is None:
            if required:
                raise ValueError('This job is not a cash booking.')
            return None
        if payment.status == Payment.Status.PAID:
            return payment
        previous = payment.status
        payment.status = Payment.Status.PAID
        payment.payload = {
            **(payment.payload or {}),
            'collected_at': timezone.now().isoformat(),
            'collected_by': str(partner.id),
        }
        payment.save(update_fields=['status', 'payload', 'updated_at'])
        BookingStatusLog.objects.create(
            booking=booking,
            from_status=previous,
            to_status='cash_collected',
            note=f'Cash collected by {partner.full_name}.',
        )
        return payment
