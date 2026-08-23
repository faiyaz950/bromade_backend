from django.contrib import admin
from django.utils.html import format_html

from apps.payments.models import Payment

from .models import Booking, BookingAssignment, BookingItem, BookingStatusLog


class BookingItemInline(admin.TabularInline):
    model = BookingItem
    extra = 0
    can_delete = False
    readonly_fields = ('service_name', 'package_name', 'unit_price', 'quantity', 'line_total')
    fields = ('service_name', 'package_name', 'unit_price', 'quantity', 'line_total')


class BookingStatusLogInline(admin.TabularInline):
    model = BookingStatusLog
    extra = 0
    can_delete = False
    readonly_fields = ('from_status', 'to_status', 'note', 'created_at')
    fields = ('from_status', 'to_status', 'note', 'created_at')


class BookingAssignmentInline(admin.TabularInline):
    model = BookingAssignment
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ('partner', 'status', 'assigned_at', 'responded_at', 'rejection_reason')
    readonly_fields = ('partner', 'status', 'assigned_at', 'responded_at', 'rejection_reason')
    verbose_name = 'Partner assignment'
    verbose_name_plural = 'Partner assignments'

    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    fields = ('gateway', 'gateway_order_id', 'gateway_payment_id', 'amount', 'status', 'created_at')
    readonly_fields = ('gateway', 'gateway_order_id', 'gateway_payment_id', 'amount', 'status', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'short_id',
        'customer_phone',
        'city',
        'scheduled_date',
        'scheduled_time',
        'status_badge',
        'assignment_badge',
        'assigned_partner',
        'amount_display',
        'created_at',
    )
    list_filter = ('status', 'assignment_status', 'city', 'scheduled_date')
    search_fields = (
        'customer__phone_number',
        'customer__first_name',
        'customer__last_name',
        'id',
        'assignments__partner__full_name',
    )
    date_hierarchy = 'scheduled_date'
    readonly_fields = ('id', 'created_at', 'updated_at', 'subtotal_amount', 'total_amount')
    autocomplete_fields = ('customer', 'address', 'city')
    inlines = [BookingItemInline, BookingAssignmentInline, PaymentInline, BookingStatusLogInline]
    fieldsets = (
        ('Customer order', {'fields': ('id', 'customer', 'status', 'assignment_status', 'notes')}),
        ('Schedule & location', {'fields': ('scheduled_date', 'scheduled_time', 'city', 'address')}),
        ('Pricing', {'fields': ('subtotal_amount', 'total_amount')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'city').prefetch_related('assignments__partner')

    @admin.display(description='ID')
    def short_id(self, obj):
        return str(obj.id)[:8]

    @admin.display(description='Customer', ordering='customer__phone_number')
    def customer_phone(self, obj):
        name = getattr(getattr(obj.customer, 'customer_profile', None), 'full_name', '')
        if name:
            return format_html('{}<br><span class="bl-meta">{}</span>', name, obj.customer.phone_number)
        return obj.customer.phone_number

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        return format_html(
            '<span class="bl-chip is-{}">{}</span>',
            obj.status,
            obj.get_status_display(),
        )

    @admin.display(description='Assignment', ordering='assignment_status')
    def assignment_badge(self, obj):
        tone = {
            Booking.AssignmentStatus.UNASSIGNED: 'draft',
            Booking.AssignmentStatus.PENDING: 'pending_payment',
            Booking.AssignmentStatus.ACCEPTED: 'confirmed',
            Booking.AssignmentStatus.REJECTED: 'cancelled',
        }.get(obj.assignment_status, obj.assignment_status)
        return format_html(
            '<span class="bl-chip is-{}">{}</span>',
            tone,
            obj.get_assignment_status_display(),
        )

    @admin.display(description='Partner')
    def assigned_partner(self, obj):
        assignment = (
            obj.assignments.filter(status__in=[BookingAssignment.Status.PENDING, BookingAssignment.Status.ACCEPTED])
            .select_related('partner')
            .order_by('-assigned_at')
            .first()
        )
        if assignment is None:
            return '—'
        return assignment.partner.full_name

    @admin.display(description='Amount', ordering='total_amount')
    def amount_display(self, obj):
        return format_html('<span class="bl-amount">₹{}</span>', obj.total_amount)


@admin.register(BookingAssignment)
class BookingAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'short_id',
        'booking_link',
        'partner_name',
        'customer_phone',
        'city_name',
        'scheduled_slot',
        'status_badge',
        'amount_display',
        'assigned_at',
        'responded_at',
    )
    list_filter = ('status', 'partner', 'booking__city', 'assigned_at')
    search_fields = (
        'partner__full_name',
        'partner__user__phone_number',
        'booking__customer__phone_number',
        'booking__id',
    )
    date_hierarchy = 'assigned_at'
    readonly_fields = ('assigned_at', 'responded_at', 'created_at', 'updated_at')
    autocomplete_fields = ('booking', 'partner')
    fieldsets = (
        ('Assignment', {'fields': ('booking', 'partner', 'status', 'rejection_reason')}),
        ('Timeline', {'fields': ('assigned_at', 'responded_at', 'created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'partner',
            'partner__user',
            'booking',
            'booking__customer',
            'booking__city',
        )

    @admin.display(description='ID')
    def short_id(self, obj):
        return str(obj.id)[:8]

    @admin.display(description='Booking')
    def booking_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'/admin/bookings/booking/{obj.booking_id}/change/',
            str(obj.booking_id)[:8],
        )

    @admin.display(description='Partner', ordering='partner__full_name')
    def partner_name(self, obj):
        return format_html(
            '{}<br><span class="bl-meta">{}</span>',
            obj.partner.full_name,
            obj.partner.user.phone_number,
        )

    @admin.display(description='Customer', ordering='booking__customer__phone_number')
    def customer_phone(self, obj):
        return obj.booking.customer.phone_number

    @admin.display(description='City', ordering='booking__city__name')
    def city_name(self, obj):
        return obj.booking.city.name

    @admin.display(description='Schedule')
    def scheduled_slot(self, obj):
        return f'{obj.booking.scheduled_date} · {obj.booking.scheduled_time.strftime("%H:%M")}'

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        tone = {
            BookingAssignment.Status.PENDING: 'pending_payment',
            BookingAssignment.Status.ACCEPTED: 'confirmed',
            BookingAssignment.Status.REJECTED: 'cancelled',
            BookingAssignment.Status.REASSIGNED: 'draft',
        }.get(obj.status, obj.status)
        return format_html(
            '<span class="bl-chip is-{}">{}</span>',
            tone,
            obj.get_status_display(),
        )

    @admin.display(description='Amount')
    def amount_display(self, obj):
        return format_html('<span class="bl-amount">₹{}</span>', obj.booking.total_amount)
