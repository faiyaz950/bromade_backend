from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Category,
    CityPackagePrice,
    HomeHeroSlide,
    Service,
    ServiceInclusion,
    ServicePackage,
    ServiceProcessStep,
)


@admin.register(HomeHeroSlide)
class HomeHeroSlideAdmin(admin.ModelAdmin):
    list_display = ('thumb', 'title', 'sort_order', 'is_active')
    list_display_links = ('thumb', 'title')
    list_editable = ('sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'subtitle')
    ordering = ('sort_order', 'created_at')
    fieldsets = (
        (
            None,
            {
                'description': 'These images fill the top slider on the customer home screen. Add as many as you need; inactive slides stay hidden.',
                'fields': ('title', 'subtitle', 'image', 'image_url'),
            },
        ),
        ('Display', {'fields': ('sort_order', 'is_active')}),
    )

    @admin.display(description='')
    def thumb(self, obj):
        url = obj.resolved_image_url()
        if not url:
            return '—'
        return format_html(
            '<img src="{}" style="width:84px;height:48px;object-fit:cover;border-radius:10px;" />',
            url,
        )


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
    extra = 3
    fields = ('kind', 'text', 'sort_order')
    ordering = ('kind', 'sort_order')
    verbose_name = 'Include / exclude item'
    verbose_name_plural = 'Includes and does not include'


class ServiceProcessStepInline(admin.StackedInline):
    model = ServiceProcessStep
    extra = 1
    fields = ('title', 'description', 'image', 'image_url', 'sort_order')
    ordering = ('sort_order',)
    verbose_name = "How it's done step"
    verbose_name_plural = "How it's done"


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('thumb', 'name', 'category', 'duration_minutes', 'is_active')
    search_fields = ('name', 'slug', 'category__name')
    list_filter = ('category', 'is_active')
    autocomplete_fields = ('category',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ServiceInclusionInline, ServiceProcessStepInline]
    fieldsets = (
        (None, {'fields': ('category', 'name', 'slug', 'image_url')}),
        (
            'Detail screen copy',
            {
                'description': (
                    'Headline and description appear under the photo. '
                    'Add Includes / Does not include rows and How it\'s done steps with the inlines below.'
                ),
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
