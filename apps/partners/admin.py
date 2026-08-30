from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from apps.bookings.models import BookingAssignment

from .models import PartnerCity, PartnerProfile, PartnerService, PartnerUnavailableDate


class PartnerCityInline(admin.TabularInline):
    model = PartnerCity
    extra = 1
    autocomplete_fields = ('city',)


class PartnerServiceInline(admin.TabularInline):
    model = PartnerService
    extra = 1
    autocomplete_fields = ('service',)


class PartnerAssignmentInline(admin.TabularInline):
    model = BookingAssignment
    fk_name = 'partner'
    extra = 0
    can_delete = False
    show_change_link = True
    verbose_name = 'Assigned job'
    verbose_name_plural = 'Assigned jobs'
    fields = ('booking', 'status', 'assigned_at', 'responded_at', 'rejection_reason')
    readonly_fields = ('booking', 'status', 'assigned_at', 'responded_at', 'rejection_reason')

    def has_add_permission(self, request, obj=None):
        return False


class PartnerUnavailableDateInline(admin.TabularInline):
    model = PartnerUnavailableDate
    extra = 0
    fields = ('date', 'note')


@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'phone_number',
        'approval_badge',
        'is_active',
        'is_available_for_assignment',
        'city_summary',
        'service_summary',
        'pending_jobs',
        'accepted_jobs',
        'created_at',
    )
    list_filter = ('approval_status', 'is_active', 'is_available_for_assignment', 'cities__city')
    search_fields = ('full_name', 'user__phone_number', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user',)
    inlines = [PartnerCityInline, PartnerServiceInline, PartnerUnavailableDateInline, PartnerAssignmentInline]
    actions = ('approve_partners', 'reject_partners', 'activate_partners', 'deactivate_partners')
    fieldsets = (
        ('Partner', {'fields': ('user', 'full_name', 'approval_status', 'approval_note')}),
        ('Operations', {'fields': ('is_active', 'is_available_for_assignment')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('user').prefetch_related('cities__city', 'services__service').annotate(
            pending_jobs_count=Count(
                'assignments',
                filter=Q(assignments__status=BookingAssignment.Status.PENDING),
            ),
            accepted_jobs_count=Count(
                'assignments',
                filter=Q(assignments__status=BookingAssignment.Status.ACCEPTED),
            ),
        )

    def save_model(self, request, obj, form, change):
        if obj.approval_status == PartnerProfile.ApprovalStatus.APPROVED:
            obj.is_active = True
        elif obj.approval_status == PartnerProfile.ApprovalStatus.REJECTED:
            obj.is_active = False
            obj.is_available_for_assignment = False
        super().save_model(request, obj, form, change)

    @admin.display(description='Phone', ordering='user__phone_number')
    def phone_number(self, obj):
        return obj.user.phone_number

    @admin.display(description='Approval', ordering='approval_status')
    def approval_badge(self, obj):
        tone = {
            PartnerProfile.ApprovalStatus.APPROVED: 'confirmed',
            PartnerProfile.ApprovalStatus.PENDING: 'draft',
            PartnerProfile.ApprovalStatus.REJECTED: 'cancelled',
        }.get(obj.approval_status, obj.approval_status)
        return format_html(
            '<span class="bl-chip is-{}">{}</span>',
            tone,
            obj.get_approval_status_display(),
        )

    @admin.display(description='Cities')
    def city_summary(self, obj):
        names = [pc.city.name for pc in obj.cities.all()[:3]]
        if not names:
            return '—'
        suffix = '…' if obj.cities.count() > 3 else ''
        return ', '.join(names) + suffix

    @admin.display(description='Services')
    def service_summary(self, obj):
        names = [ps.service.name for ps in obj.services.all()[:2]]
        if not names:
            return '—'
        suffix = '…' if obj.services.count() > 2 else ''
        return ', '.join(names) + suffix

    @admin.display(description='Pending jobs', ordering='pending_jobs_count')
    def pending_jobs(self, obj):
        return obj.pending_jobs_count

    @admin.display(description='Accepted jobs', ordering='accepted_jobs_count')
    def accepted_jobs(self, obj):
        return obj.accepted_jobs_count

    @admin.action(description='Approve selected partners')
    def approve_partners(self, request, queryset):
        updated = queryset.update(
            approval_status=PartnerProfile.ApprovalStatus.APPROVED,
            is_active=True,
            updated_at=timezone.now(),
        )
        self.message_user(request, f'{updated} partner(s) approved.', messages.SUCCESS)

    @admin.action(description='Reject selected partners')
    def reject_partners(self, request, queryset):
        updated = queryset.update(
            approval_status=PartnerProfile.ApprovalStatus.REJECTED,
            is_active=False,
            is_available_for_assignment=False,
            updated_at=timezone.now(),
        )
        self.message_user(request, f'{updated} partner(s) rejected.', messages.WARNING)

    @admin.action(description='Activate selected partners')
    def activate_partners(self, request, queryset):
        updated = queryset.filter(approval_status=PartnerProfile.ApprovalStatus.APPROVED).update(
            is_active=True,
            updated_at=timezone.now(),
        )
        self.message_user(request, f'{updated} approved partner(s) activated.', messages.SUCCESS)

    @admin.action(description='Deactivate selected partners')
    def deactivate_partners(self, request, queryset):
        updated = queryset.update(
            is_active=False,
            is_available_for_assignment=False,
            updated_at=timezone.now(),
        )
        self.message_user(request, f'{updated} partner(s) deactivated.', messages.WARNING)
