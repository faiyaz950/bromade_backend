from django.contrib import admin
from django.utils.html import format_html

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'gateway_order_id',
        'booking',
        'amount_display',
        'method',
        'status_badge',
        'created_at',
    )
    search_fields = ('gateway_order_id', 'gateway_payment_id', 'booking__id')
    list_filter = ('status', 'method', 'gateway', 'created_at')
    date_hierarchy = 'created_at'
    autocomplete_fields = ('booking',)
    readonly_fields = ('created_at', 'updated_at', 'payload')
    fieldsets = (
        ('Payment', {'fields': ('booking', 'method', 'status', 'amount', 'currency')}),
        ('Gateway', {'fields': ('gateway', 'gateway_order_id', 'gateway_payment_id', 'payload')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Amount', ordering='amount')
    def amount_display(self, obj):
        return format_html('<span class="bl-amount">₹{}</span>', obj.amount)

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        tone = {
            'paid': 'confirmed',
            'created': 'draft',
            'cash_pending': 'draft',
            'failed': 'cancelled',
        }.get(obj.status, obj.status)
        return format_html(
            '<span class="bl-chip is-{}">{}</span>',
            tone,
            obj.get_status_display(),
        )
