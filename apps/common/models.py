import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class AppRelease(TimeStampedModel):
    """Store versions the mobile apps compare against to prompt for updates."""

    class App(models.TextChoices):
        CUSTOMER = 'customer', 'Customer app'
        PARTNER = 'partner', 'Demess Legends (partner app)'

    class Platform(models.TextChoices):
        ANDROID = 'android', 'Android'
        IOS = 'ios', 'iOS'

    version_help = 'Like 1.4.0 — the version name from pubspec.yaml, without the +build number.'

    app = models.CharField(max_length=20, choices=App.choices, default=App.CUSTOMER)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    latest_version = models.CharField(
        max_length=20,
        help_text=f'Newest version in the store. Older apps see an optional "Update" card. {version_help}',
    )
    min_supported_version = models.CharField(
        max_length=20,
        blank=True,
        help_text=f'Apps older than this are blocked until they update. Leave blank to never force. {version_help}',
    )
    store_url = models.URLField(help_text='Play Store / App Store page the Update button opens.')
    message = models.CharField(
        max_length=220,
        blank=True,
        help_text='Optional text shown in the prompt, e.g. what is new.',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['app', 'platform'], name='unique_app_release_per_platform'),
        ]
        ordering = ['app', 'platform']
        verbose_name = 'App release'

    def __str__(self):
        return f'{self.get_app_display()} · {self.get_platform_display()} · {self.latest_version}'


class PushCampaign(UUIDModel):
    """A notification the team writes in admin and sends now or later."""

    class Audience(models.TextChoices):
        CUSTOMERS = 'customers', 'Customers (customer app)'
        PARTNERS = 'partners', 'Professionals (Demess Legends app)'

    class Target(models.TextChoices):
        EVERYONE = 'everyone', 'Everyone'
        CITY = 'city', 'Everyone in one city'
        PERSON = 'person', 'One person'

    class Screen(models.TextChoices):
        HOME = 'home', 'Home'
        SERVICE = 'service', 'A service'
        PACKAGE = 'package', 'A package'
        REFER = 'refer', 'Refer & earn'

    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    title = models.CharField(max_length=65, help_text='Short and clear, e.g. "20% off AC service this week".')
    body = models.CharField(max_length=240, help_text='The message under the title.')
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.CUSTOMERS)
    target = models.CharField(max_length=20, choices=Target.choices, default=Target.EVERYONE, verbose_name='send to')
    city = models.ForeignKey(
        'locations.City',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='push_campaigns',
        help_text='For "Everyone in one city". Customers with an address or booking there; '
        'professionals who serve it.',
    )
    recipient = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='phone or email',
        help_text='For "One person", e.g. 9876543210 or name@gmail.com.',
    )
    screen = models.CharField(
        max_length=20,
        choices=Screen.choices,
        default=Screen.HOME,
        verbose_name='opens on tap',
        help_text='Professionals always land on their home screen.',
    )
    service = models.ForeignKey(
        'catalog.Service',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='push_campaigns',
    )
    package = models.ForeignKey(
        'catalog.ServicePackage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='push_campaigns',
    )
    send_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='schedule for',
        help_text='Leave blank to send right away.',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED, editable=False)
    sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    devices = models.PositiveIntegerField(default=0, editable=False, verbose_name='phones targeted')
    delivered = models.PositiveIntegerField(default=0, editable=False)
    failed = models.PositiveIntegerField(default=0, editable=False)
    error = models.CharField(max_length=255, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='+',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'send_at'])]
        verbose_name = 'Push notification'
        verbose_name_plural = 'Push notifications'

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        errors = {}
        if self.target != self.Target.CITY:
            self.city = None
        elif self.city is None:
            errors['city'] = 'Pick the city.'
        if self.target != self.Target.PERSON:
            self.recipient = ''
        elif not self.recipient.strip():
            errors['recipient'] = 'Enter their phone number or email.'
        else:
            from .campaigns import find_recipient_tokens

            self.recipient = self.recipient.strip()
            if not find_recipient_tokens(self.audience, self.recipient):
                app = 'partner' if self.audience == self.Audience.PARTNERS else 'customer'
                errors['recipient'] = f'No one with this phone or email is signed in to the {app} app.'

        if self.audience == self.Audience.PARTNERS:
            self.screen = self.Screen.HOME
        if self.screen != self.Screen.SERVICE:
            self.service = None
        elif self.service is None:
            errors['service'] = 'Pick the service to open.'
        if self.screen != self.Screen.PACKAGE:
            self.package = None
        elif self.package is None:
            errors['package'] = 'Pick the package to open.'

        if self.send_at and self.send_at < timezone.now() - timedelta(minutes=1):
            errors['send_at'] = 'This time has passed. Pick a later time or leave it blank to send now.'
        if errors:
            raise ValidationError(errors)
