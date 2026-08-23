from django.contrib import admin

from .models import Address, City


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'slug', 'is_active')
    list_filter = ('state', 'is_active')
    search_fields = ('name', 'state', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('label', 'contact_name', 'user', 'city', 'is_default', 'updated_at')
    search_fields = ('label', 'contact_name', 'user__phone_number', 'city__name', 'line1')
    list_filter = ('city', 'is_default')
    autocomplete_fields = ('user', 'city')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Owner', {'fields': ('user', 'label', 'is_default')}),
        ('Contact', {'fields': ('contact_name', 'contact_phone')}),
        ('Location', {'fields': ('city', 'line1', 'line2', 'landmark', 'pincode')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
