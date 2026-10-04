from django.db import transaction
from django.utils import timezone

from .models import SupportMessage, SupportTicket


def _notify_customer(ticket: SupportTicket, body: str) -> None:
    from apps.accounts.models import UserDeviceToken
    from apps.common.push import send_push

    send_push(
        UserDeviceToken.objects.filter(user_id=ticket.user_id).values_list('token', flat=True),
        title='Bayti Support replied',
        body=body[:140],
        data={'type': 'support', 'ticket_id': str(ticket.id)},
    )


class SupportService:
    @staticmethod
    @transaction.atomic
    def start_chat(*, user, topic, body, booking=None) -> SupportTicket:
        ticket = SupportTicket.objects.create(user=user, booking=booking, topic=topic)
        SupportService.post(ticket, sender=SupportMessage.Sender.CUSTOMER, body=body, author=user)
        return ticket

    @staticmethod
    def post(ticket: SupportTicket, *, sender, body, author=None) -> SupportMessage:
        body = (body or '').strip()
        if not body:
            raise ValueError('Type a message first.')
        message = SupportMessage.objects.create(ticket=ticket, sender=sender, body=body, author=author)
        ticket.last_message_at = message.created_at
        fields = ['last_message_at', 'updated_at']
        if sender == SupportMessage.Sender.SUPPORT:
            ticket.admin_read_at = message.created_at
            fields.append('admin_read_at')
        else:
            ticket.customer_read_at = message.created_at
            fields.append('customer_read_at')
            if ticket.status == SupportTicket.Status.RESOLVED:
                ticket.status = SupportTicket.Status.OPEN
                fields.append('status')
        ticket.save(update_fields=fields)
        if sender == SupportMessage.Sender.SUPPORT:
            _notify_customer(ticket, body)
        return message

    @staticmethod
    def mark_read(ticket: SupportTicket, *, by_admin: bool) -> None:
        field = 'admin_read_at' if by_admin else 'customer_read_at'
        setattr(ticket, field, timezone.now())
        ticket.save(update_fields=[field, 'updated_at'])

    @staticmethod
    def set_status(ticket: SupportTicket, status, *, author=None) -> None:
        if ticket.status == status:
            return
        ticket.status = status
        ticket.save(update_fields=['status', 'updated_at'])
        if status == SupportTicket.Status.RESOLVED:
            SupportService.post(
                ticket,
                sender=SupportMessage.Sender.SUPPORT,
                body='We have marked this chat as resolved. Reply here any time if you still need help.',
                author=author,
            )
