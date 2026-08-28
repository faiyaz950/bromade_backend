from django.contrib import admin

from .models import Address, City


@admin.action(description='Mark selected cities as services live')
def make_services_live(modeladmin, request, queryset):
    queryset.update(is_active=True)


@admin.action(description='Mark selected cities as available soon')
def make_available_soon(modeladmin, request, queryset):
    queryset.update(is_active=False)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'is_active', 'aliases', 'service_radius_km')
    list_editable = ('is_active',)
    list_filter = ('is_active', 'state')
    search_fields = ('name', 'state', 'slug', 'aliases')
    prepopulated_fields = {'slug': ('name',)}
    actions = (make_services_live, make_available_soon)
    list_display_links = ('name',)
    fieldsets = (
        (
            'City',
            {
                'description': (
                    'Customers whose GPS matches this city can book only when “Services live” is on. '
                    'Turn it off to show the Available soon screen.'
                ),
                'fields': ('name', 'slug', 'state', 'is_active'),
            },
        ),
        (
            'Matching',
            {
                'description': (
                    'GPS is matched by name aliases and, if you set a pin, by distance. '
                    'Add extra names like Bombay or New Delhi so suburbs still resolve.'
                ),
                'fields': ('aliases', 'latitude', 'longitude', 'service_radius_km'),
            },
        ),
        (
            'Available soon',
            {
                'fields': ('coming_soon_message',),
            },
        ),
    )


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
