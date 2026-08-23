from django.contrib import admin
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils.html import format_html

from apps.bookings.models import Booking
from apps.locations.models import Address

from .models import CustomerProfile


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
