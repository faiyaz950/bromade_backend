import re

from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .campaigns import campaign_tokens, send_in_background
from .models import AppRelease, PushCampaign

_VERSION = re.compile(r'^\d+(\.\d+){0,2}$')


class AppReleaseForm(forms.ModelForm):
    class Meta:
        model = AppRelease
        fields = '__all__'

    def _clean_version(self, field):
        value = (self.cleaned_data.get(field) or '').strip()
        if value and not _VERSION.match(value):
            raise forms.ValidationError('Use numbers like 1.4.0.')
        return value

    def clean_latest_version(self):
        return self._clean_version('latest_version')

    def clean_min_supported_version(self):
        return self._clean_version('min_supported_version')


@admin.register(AppRelease)
class AppReleaseAdmin(admin.ModelAdmin):
    form = AppReleaseForm
    list_display = ('app', 'platform', 'latest_version', 'min_supported_version', 'updated_at')
    list_filter = ('app', 'platform')


_STATUS_COLORS = {
    PushCampaign.Status.SCHEDULED: '#B7791F',
    PushCampaign.Status.SENDING: '#2B6CB0',
    PushCampaign.Status.SENT: '#2F855A',
    PushCampaign.Status.FAILED: '#C53030',
    PushCampaign.Status.CANCELLED: '#718096',
}


@admin.register(PushCampaign)
class PushCampaignAdmin(admin.ModelAdmin):
    list_display = ('title', 'who', 'status_badge', 'when', 'result')
    list_filter = ('status', 'audience', 'target')
    search_fields = ('title', 'body', 'recipient')
    autocomplete_fields = ('service', 'package')
    actions = ('send_now', 'cancel')
    fieldsets = (
        ('Message', {'fields': ('title', 'body')}),
        ('Who gets it', {'fields': ('audience', 'target', 'city', 'recipient')}),
        ('When they tap it', {'fields': ('screen', 'service', 'package')}),
        ('When to send', {'fields': ('send_at',)}),
        ('Result', {'fields': ('status', 'reach', 'delivered', 'failed', 'error', 'sent_at', 'created_by')}),
    )
    readonly_fields = ('status', 'reach', 'delivered', 'failed', 'error', 'sent_at', 'created_by')

    class Media:
        js = ('admin/push_campaign.js',)

    def get_fieldsets(self, request, obj=None):
        # The result section means nothing before the first save.
        return self.fieldsets if obj else self.fieldsets[:-1]

    def has_change_permission(self, request, obj=None):
        # Once it has gone out (or been cancelled) it is a record, not a draft.
        allowed = super().has_change_permission(request, obj)
        return allowed and (obj is None or obj.status == PushCampaign.Status.SCHEDULED)

    @admin.display(description='Sent to')
    def who(self, obj):
        if obj.target == PushCampaign.Target.CITY:
            place = obj.city.name if obj.city else 'a city'
            return f'{obj.get_audience_display().split(" (")[0]} in {place}'
        if obj.target == PushCampaign.Target.PERSON:
            return obj.recipient
        return f'All {obj.get_audience_display().split(" (")[0].lower()}'

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        return format_html(
            '<span style="color:#fff;background:{};padding:2px 8px;border-radius:10px;font-size:11px">{}</span>',
            _STATUS_COLORS.get(obj.status, '#718096'),
            obj.get_status_display(),
        )

    @admin.display(description='When', ordering='send_at')
    def when(self, obj):
        moment = obj.sent_at or obj.send_at
        return timezone.localtime(moment).strftime('%d %b %Y, %I:%M %p') if moment else '—'

    @admin.display(description='Delivered')
    def result(self, obj):
        if obj.status in (PushCampaign.Status.SENT, PushCampaign.Status.FAILED) and obj.devices:
            return f'{obj.delivered} of {obj.devices} phones'
        return '—'

    @admin.display(description='Phones')
    def reach(self, obj):
        if obj.status == PushCampaign.Status.SCHEDULED:
            return f'{len(campaign_tokens(obj))} phones right now (counted again when it sends)'
        return f'{obj.devices} phones targeted'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        if obj.send_at is None:
            obj.send_at = timezone.now()
        super().save_model(request, obj, form, change)
        if obj.send_at <= timezone.now():
            send_in_background(obj.pk)

    def response_add(self, request, obj, post_url_continue=None):
        self._report(request, obj)
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        self._report(request, obj)
        return super().response_change(request, obj)

    def _report(self, request, obj):
        if obj.send_at > timezone.now():
            when = timezone.localtime(obj.send_at).strftime('%d %b, %I:%M %p')
            self.message_user(request, f'Scheduled for {when}.', messages.SUCCESS)
        else:
            self.message_user(
                request, 'Sending now. Open it again in a few seconds to see how many phones got it.', messages.SUCCESS
            )

    @admin.action(description='Send selected now')
    def send_now(self, request, queryset):
        due = list(queryset.filter(status=PushCampaign.Status.SCHEDULED).values_list('pk', flat=True))
        PushCampaign.objects.filter(pk__in=due).update(send_at=timezone.now())
        for pk in due:
            send_in_background(pk)
        self.message_user(request, f'Sending {len(due)} notification(s).', messages.SUCCESS)

    @admin.action(description='Cancel selected (if not sent yet)')
    def cancel(self, request, queryset):
        count = queryset.filter(status=PushCampaign.Status.SCHEDULED).update(
            status=PushCampaign.Status.CANCELLED, updated_at=timezone.now()
        )
        self.message_user(request, f'Cancelled {count} notification(s).', messages.SUCCESS)
