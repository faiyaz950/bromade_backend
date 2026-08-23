from django.contrib import admin
from django.utils.html import format_html

from .models import Category, CityPackagePrice, Service, ServiceInclusion, ServicePackage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('thumb', 'name', 'slug', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'description', 'image_url')}),
        ('Display', {'fields': ('sort_order', 'is_active')}),
    )

    @admin.display(description='')
    def thumb(self, obj):
        if not obj.image_url:
            return '—'
        return format_html(
            '<img src="{}" style="width:42px;height:42px;object-fit:cover;border-radius:10px;" />',
            obj.image_url,
        )


class ServiceInclusionInline(admin.TabularInline):
    model = ServiceInclusion
    extra = 4
    fields = ('kind', 'text', 'sort_order')
    ordering = ('kind', 'sort_order')


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('thumb', 'name', 'category', 'duration_minutes', 'is_active')
    search_fields = ('name', 'slug', 'category__name')
    list_filter = ('category', 'is_active')
    autocomplete_fields = ('category',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ServiceInclusionInline]
    fieldsets = (
        (None, {'fields': ('category', 'name', 'slug', 'image_url')}),
        (
            'Detail screen copy',
            {
                'description': 'Headline, description, and the include / does not include rows below appear on the customer app service screen.',
                'fields': ('headline', 'short_description', 'description'),
            },
        ),
        ('Display', {'fields': ('duration_minutes', 'is_active')}),
    )

    @admin.display(description='')
    def thumb(self, obj):
        if not obj.image_url:
            return '—'
        return format_html(
            '<img src="{}" style="width:42px;height:42px;object-fit:cover;border-radius:10px;" />',
            obj.image_url,
        )


@admin.register(ServicePackage)
class ServicePackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'service', 'base_price', 'discounted_price', 'duration_minutes', 'is_active')
    search_fields = ('name', 'slug', 'service__name')
    list_filter = ('service__category', 'is_active')
    autocomplete_fields = ('service',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(CityPackagePrice)
class CityPackagePriceAdmin(admin.ModelAdmin):
    list_display = ('city', 'package', 'price', 'discounted_price', 'is_active')
    search_fields = ('city__name', 'package__name')
    list_filter = ('city', 'is_active')
    autocomplete_fields = ('city', 'package')
