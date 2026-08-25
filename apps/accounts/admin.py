from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import OTPRequest, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ('-created_at',)
    list_display = ('phone_number', 'email', 'full_name', 'account_type', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'is_superuser')
    search_fields = ('phone_number', 'email', 'google_id', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined', 'created_at')
    fieldsets = (
        ('Account', {'fields': ('phone_number', 'email', 'google_id', 'password')}),
        ('Profile', {'fields': ('first_name', 'last_name')}),
        ('Access', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Timestamps', {'fields': ('last_login', 'date_joined', 'created_at')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('phone_number', 'password1', 'password2', 'is_staff', 'is_active'),
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer_profile', 'partner_profile')

    @admin.display(description='Name', ordering='first_name')
    def full_name(self, obj):
        name = f'{obj.first_name} {obj.last_name}'.strip()
        if hasattr(obj, 'customer_profile') and obj.customer_profile.full_name:
            return obj.customer_profile.full_name
        if hasattr(obj, 'partner_profile') and obj.partner_profile.full_name:
            return obj.partner_profile.full_name
        return name or '—'

    @admin.display(description='Type')
    def account_type(self, obj):
        if hasattr(obj, 'partner_profile'):
            return format_html('<span class="bl-chip is-pending_payment">Partner</span>')
        if hasattr(obj, 'customer_profile'):
            return format_html('<span class="bl-chip is-confirmed">Customer</span>')
        if obj.is_staff:
            return format_html('<span class="bl-chip is-draft">Staff</span>')
        return '—'


@admin.register(OTPRequest)
class OTPRequestAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'code_badge', 'channel', 'is_used', 'created_at', 'expires_at')
    search_fields = ('phone_number', 'code')
    list_filter = ('channel', 'is_used', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'

    @admin.display(description='OTP')
    def code_badge(self, obj):
        return format_html('<code style="font-weight:700;letter-spacing:0.08em;">{}</code>', obj.code)
