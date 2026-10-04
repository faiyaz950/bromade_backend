from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import format_html

from apps.bookings.models import Booking
from apps.locations.models import Address

from .models import CustomerProfile, SupportMessage, SupportTicket
from .support import SupportService


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'phone_number',
        'email',
        'orders_count',
        'confirmed_orders',
        'total_spent_display',
        'created_at',
    )
    search_fields = ('full_name', 'email', 'user__phone_number', 'user__first_name', 'user__last_name')
    list_filter = ('created_at',)
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at', 'addresses_panel', 'orders_panel')
    fieldsets = (
        ('Customer', {'fields': ('user', 'full_name', 'email')}),
        ('Saved addresses', {'fields': ('addresses_panel',)}),
        ('Customer orders', {'fields': ('orders_panel',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').annotate(
            orders_count=Count('user__bookings', distinct=True),
            confirmed_orders_count=Count(
                'user__bookings',
                filter=Q(user__bookings__status=Booking.Status.CONFIRMED),
                distinct=True,
            ),
            total_spent=Sum('user__bookings__total_amount'),
        )

    @admin.display(description='Phone', ordering='user__phone_number')
    def phone_number(self, obj):
        return obj.user.phone_number

    @admin.display(description='Orders', ordering='orders_count')
    def orders_count(self, obj):
        return obj.orders_count

    @admin.display(description='Confirmed', ordering='confirmed_orders_count')
    def confirmed_orders(self, obj):
        return obj.confirmed_orders_count

    @admin.display(description='Total spent', ordering='total_spent')
    def total_spent_display(self, obj):
        total = obj.total_spent or 0
        return format_html('<span class="bl-amount">₹{}</span>', total)

    @admin.display(description='Addresses')
    def addresses_panel(self, obj):
        addresses = Address.objects.filter(user=obj.user).select_related('city')
        if not addresses:
            return 'No saved addresses.'
        rows = []
        for address in addresses:
            default = ' · Default' if address.is_default else ''
            rows.append(
                f'<li><strong>{address.label}</strong>{default}<br>'
                f'<span class="bl-meta">{address.line1}, {address.city.name} · {address.pincode}</span></li>'
            )
        return format_html('<ul class="bl-detail-list">{}</ul>', format_html(''.join(rows)))

    @admin.display(description='Orders')
    def orders_panel(self, obj):
        bookings = (
            Booking.objects.filter(customer=obj.user)
            .select_related('city')
            .order_by('-created_at')[:12]
        )
        if not bookings:
            return 'No orders yet.'
        rows = []
        for booking in bookings:
            url = reverse('admin:bookings_booking_change', args=[booking.pk])
            rows.append(
                f'<li><a href="{url}"><strong>{booking.scheduled_date} · {booking.scheduled_time.strftime("%H:%M")}</strong></a><br>'
                f'<span class="bl-meta">{booking.city.name} · {booking.get_status_display()} · '
                f'{booking.get_assignment_status_display()}</span><br>'
                f'<span class="bl-amount">₹{booking.total_amount}</span></li>'
            )
        all_url = reverse('admin:bookings_booking_changelist') + f'?customer__id__exact={obj.user_id}'
        return format_html(
            '<ul class="bl-detail-list">{}</ul><p><a href="{}">View all customer orders</a></p>',
            format_html(''.join(rows)),
            all_url,
        )



@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('chat_title', 'customer_display', 'booking_link', 'status_badge', 'unread_badge', 'last_message_at')
    list_filter = ('status', 'created_at')
    search_fields = ('topic', 'messages__body', 'user__phone_number', 'user__first_name', 'user__last_name')
    list_per_page = 40

    class Media:
        css = {'all': ('admin/css/support_chat.css',)}

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'user__customer_profile', 'booking').distinct()

    def has_add_permission(self, request):
        return False

    @admin.display(description='Chat', ordering='topic')
    def chat_title(self, obj):
        last = obj.messages.order_by('-created_at').first()
        preview = (last.body[:70] + ('…' if len(last.body) > 70 else '')) if last else ''
        return format_html(
            '<strong>{}</strong><br><span class="bl-meta">{}</span>',
            obj.topic,
            preview,
        )

    @admin.display(description='Customer', ordering='user__first_name')
    def customer_display(self, obj):
        return _customer_name(obj.user)

    @admin.display(description='Booking')
    def booking_link(self, obj):
        if obj.booking_id is None:
            return '—'
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:bookings_booking_change', args=[obj.booking_id]),
            str(obj.booking_id)[:8].upper(),
        )

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        resolved = obj.status == SupportTicket.Status.RESOLVED
        return format_html(
            '<span class="bl-pill" style="background:{};color:{}">{}</span>',
            '#e6f5ec' if resolved else '#fff2db',
            '#16794a' if resolved else '#9a5a00',
            obj.get_status_display(),
        )

    @admin.display(description='New')
    def unread_badge(self, obj):
        count = obj.unread_for_admin()
        if not count:
            return ''
        return format_html('<span class="bl-chat-unread">{}</span>', count)

    def get_urls(self):
        custom = [
            path(
                '<uuid:object_id>/poll/',
                self.admin_site.admin_view(self.poll_view),
                name='customers_supportticket_poll',
            ),
        ]
        return custom + super().get_urls()

    def change_view(self, request, object_id, form_url='', extra_context=None):
        ticket = self.get_object(request, object_id)
        if ticket is None:
            return self._get_obj_does_not_exist_redirect(request, self.opts, object_id)
        if not self.has_view_or_change_permission(request, ticket):
            raise PermissionDenied
        can_reply = self.has_change_permission(request, ticket)

        if request.method == 'POST' and can_reply:
            action = request.POST.get('action', 'send')
            if action == 'resolve':
                SupportService.set_status(ticket, SupportTicket.Status.RESOLVED, author=request.user)
                messages.success(request, 'Chat marked as resolved.')
            elif action == 'reopen':
                SupportService.set_status(ticket, SupportTicket.Status.OPEN, author=request.user)
                messages.success(request, 'Chat reopened.')
            else:
                try:
                    SupportService.post(
                        ticket,
                        sender=SupportMessage.Sender.SUPPORT,
                        body=request.POST.get('body', '')[:2000],
                        author=request.user,
                    )
                except ValueError as exc:
                    messages.error(request, str(exc))
            return HttpResponseRedirect(request.path)

        SupportService.mark_read(ticket, by_admin=True)
        booking = ticket.booking
        item = booking.items.first() if booking else None
        context = {
            **self.admin_site.each_context(request),
            'opts': self.opts,
            'title': ticket.topic,
            'subtitle': 'Support chat',
            'ticket': ticket,
            'chat_messages': ticket.messages.select_related('author'),
            'customer_name': _customer_name(ticket.user),
            'customer_phone': ticket.user.phone_number or '',
            'booking': booking,
            'booking_item': item,
            'booking_url': reverse('admin:bookings_booking_change', args=[booking.id]) if booking else '',
            'poll_url': reverse('admin:customers_supportticket_poll', args=[ticket.id]),
            'can_reply': can_reply,
            'quick_replies': QUICK_REPLIES,
            'other_open': SupportTicket.objects.filter(status=SupportTicket.Status.OPEN)
            .exclude(pk=ticket.pk)
            .select_related('user', 'user__customer_profile')[:12],
            **(extra_context or {}),
        }
        return TemplateResponse(request, 'admin/customers/support_chat.html', context)

    def poll_view(self, request, object_id):
        ticket = self.get_object(request, str(object_id))
        if ticket is None or not self.has_view_or_change_permission(request, ticket):
            return JsonResponse({'messages': []}, status=404)
        qs = ticket.messages.all()
        after = parse_datetime(request.GET.get('after', '') or '')
        if after is not None:
            qs = qs.filter(created_at__gt=after)
        new = list(qs)
        if any(m.sender == SupportMessage.Sender.CUSTOMER for m in new):
            SupportService.mark_read(ticket, by_admin=True)
        return JsonResponse(
            {
                'status': ticket.status,
                'messages': [
                    {
                        'id': str(m.id),
                        'sender': m.sender,
                        'body': m.body,
                        'created_at': m.created_at.isoformat(),
                        'time': timezone.localtime(m.created_at).strftime('%d %b, %I:%M %p'),
                    }
                    for m in new
                ],
            }
        )


QUICK_REPLIES = [
    'Hi! Thanks for reaching out. Let me check this for you.',
    'Sorry for the trouble. Your professional is on the way and will reach shortly.',
    'Your refund has been started. It reaches your account in 5–7 working days.',
    'Could you share a little more detail so we can help faster?',
    'Glad we could help! Is there anything else you need?',
]


def _customer_name(user):
    profile = getattr(user, 'customer_profile', None)
    name = (getattr(profile, 'full_name', '') or f'{user.first_name} {user.last_name}').strip()
    return name or user.phone_number or 'Customer'
