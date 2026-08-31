from django import forms
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from apps.bookings.models import BookingAssignment

from .models import PartnerCity, PartnerProfile, PartnerService, PartnerUnavailableDate, WalletTransaction
from .wallet_service import WalletService


class PartnerWalletCreditForm(forms.ModelForm):
    add_wallet_amount = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        label='Add wallet amount',
        help_text='Partner paid you this amount in real money. It is added to their wallet 1:1.',
    )
    wallet_note = forms.CharField(
        required=False,
        max_length=255,
        label='Wallet note',
        help_text='Optional. Example: UPI received 12 Mar.',
    )

    class Meta:
        model = PartnerProfile
        fields = '__all__'


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


class WalletTransactionInline(admin.TabularInline):
    model = WalletTransaction
    extra = 0
    can_delete = False
    show_change_link = False
    verbose_name = 'Wallet entry'
    verbose_name_plural = 'Wallet history'
    fields = ('created_at', 'entry_type', 'amount', 'balance_after', 'note', 'booking')
    readonly_fields = fields
    ordering = ('-created_at',)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    form = PartnerWalletCreditForm
    list_display = (
        'full_name',
        'phone_number',
        'approval_badge',
        'wallet_balance',
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
    readonly_fields = ('created_at', 'updated_at', 'wallet_balance')
    autocomplete_fields = ('user',)
    inlines = [
        PartnerCityInline,
        PartnerServiceInline,
        PartnerUnavailableDateInline,
        WalletTransactionInline,
        PartnerAssignmentInline,
    ]
    actions = ('approve_partners', 'reject_partners', 'activate_partners', 'deactivate_partners')
    fieldsets = (
        ('Partner', {'fields': ('user', 'full_name', 'email', 'approval_status', 'approval_note')}),
        ('Home & KYC', {'fields': ('address_line', 'pincode', 'years_experience', 'aadhaar_number', 'pan_number')}),
        (
            'Payout',
            {
                'fields': (
                    'upi_id',
                    'upi_phone',
                    'bank_account_holder',
                    'bank_account_number',
                    'bank_ifsc',
                )
            },
        ),
        (
            'Wallet',
            {
                'fields': ('wallet_balance', 'add_wallet_amount', 'wallet_note'),
                'description': 'Partner pays you real money. Add the same amount here. They need 30% of a job in this wallet to accept it.',
            },
        ),
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
        amount = form.cleaned_data.get('add_wallet_amount')
        if amount:
            WalletService.credit(
                partner=obj,
                amount=amount,
                note=form.cleaned_data.get('wallet_note') or f'Admin credit by {request.user}',
                created_by=request.user,
            )
            self.message_user(
                request,
                f'Added ₹{amount} to wallet. New balance ₹{obj.wallet_balance}.',
                messages.SUCCESS,
            )

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

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if obj.approval_status == PartnerProfile.ApprovalStatus.APPROVED and not obj.registration_is_complete:
            obj.approval_status = PartnerProfile.ApprovalStatus.PENDING
            obj.is_active = False
            obj.save(update_fields=['approval_status', 'is_active', 'updated_at'])
            self.message_user(
                request,
                'This partner still needs home address, Aadhaar, cities, services, and UPI or bank details before approval.',
                messages.WARNING,
            )
        elif obj.approval_status == PartnerProfile.ApprovalStatus.APPROVED:
            from .assignment_service import AssignmentService

            assigned = AssignmentService.assign_open_confirmed_bookings()
            if assigned:
                self.message_user(request, f'{assigned} open booking(s) assigned after this approval.', messages.SUCCESS)

    @admin.action(description='Approve selected partners')
    def approve_partners(self, request, queryset):
        from .assignment_service import AssignmentService

        approved = 0
        skipped = 0
        for partner in queryset:
            if not partner.registration_is_complete:
                skipped += 1
                continue
            partner.approval_status = PartnerProfile.ApprovalStatus.APPROVED
            partner.is_active = True
            partner.save(update_fields=['approval_status', 'is_active', 'updated_at'])
            approved += 1
        assigned = AssignmentService.assign_open_confirmed_bookings() if approved else 0
        if approved:
            self.message_user(
                request,
                f'{approved} partner(s) approved. {assigned} open booking(s) assigned.',
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f'{skipped} partner(s) skipped — complete registration first.',
                messages.WARNING,
            )

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
