from django.contrib import admin
from django.utils.html import format_html

from .models import Coupon, CouponRedemption


class CouponRedemptionInline(admin.TabularInline):
    model = CouponRedemption
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ('user', 'booking', 'discount_amount', 'created_at')
    readonly_fields = ('user', 'booking', 'discount_amount', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'title',
        'discount_display',
        'validity_display',
        'usage_display',
        'active_badge',
        'created_at',
    )
    list_filter = ('is_active', 'discount_type', 'valid_until')
    search_fields = ('code', 'title', 'description')
    filter_horizontal = ('cities', 'services', 'packages')
    inlines = [CouponRedemptionInline]
    readonly_fields = ('id', 'created_at', 'updated_at', 'usage_display')
    fieldsets = (
        (
            'Coupon',
            {
                'description': 'Customers enter the code on the Confirm Booking screen in the app.',
                'fields': ('code', 'title', 'description', 'is_active'),
            },
        ),
        (
            'Discount',
            {
                'fields': (
                    'discount_type',
                    'discount_value',
                    'min_order_amount',
                    'max_discount_amount',
                ),
            },
        ),
        (
            'Limits & dates',
            {
                'fields': (
                    'usage_limit',
                    'usage_limit_per_user',
                    'valid_from',
                    'valid_until',
                    'usage_display',
                ),
            },
        ),
        (
            'Where it applies',
            {
                'description': 'Leave these empty to apply the coupon to every city, service, and package.',
                'fields': ('cities', 'services', 'packages'),
                'classes': ('collapse',),
            },
        ),
        ('Record', {'fields': ('id', 'created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('redemptions')

    @admin.display(description='Discount')
    def discount_display(self, obj):
        if obj.discount_type == Coupon.DiscountType.PERCENTAGE:
            label = f'{obj.discount_value:.0f}% off'
            if obj.max_discount_amount:
                label += f' (max ₹{obj.max_discount_amount:.0f})'
        else:
            label = f'₹{obj.discount_value:.0f} off'
        if obj.min_order_amount:
            label += f' · min ₹{obj.min_order_amount:.0f}'
        return label

    @admin.display(description='Validity')
    def validity_display(self, obj):
        if obj.valid_from and obj.valid_until:
            return f'{obj.valid_from} → {obj.valid_until}'
        if obj.valid_until:
            return f'Until {obj.valid_until}'
        if obj.valid_from:
            return f'From {obj.valid_from}'
        return 'No expiry'

    @admin.display(description='Usage')
    def usage_display(self, obj):
        used = obj.times_used()
        if obj.usage_limit is None:
            return f'{used} used · unlimited'
        return f'{used} / {obj.usage_limit} used'

    @admin.display(description='Status', boolean=False, ordering='is_active')
    def active_badge(self, obj):
        if not obj.is_currently_valid():
            return format_html('<span class="bl-chip is-cancelled">Inactive</span>')
        return format_html('<span class="bl-chip is-confirmed">Active</span>')


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'customer_phone', 'discount_amount', 'booking_link', 'created_at')
    list_filter = ('coupon', 'created_at')
    search_fields = ('coupon__code', 'user__phone_number', 'booking__id')
    autocomplete_fields = ('coupon', 'user', 'booking')
    readonly_fields = ('coupon', 'user', 'booking', 'discount_amount', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('coupon', 'user', 'booking')

    @admin.display(description='Customer', ordering='user__phone_number')
    def customer_phone(self, obj):
        return obj.user.phone_number

    @admin.display(description='Booking')
    def booking_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            f'/admin/bookings/booking/{obj.booking_id}/change/',
            str(obj.booking_id)[:8],
        )
