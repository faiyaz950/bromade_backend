from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel, UUIDModel


class UserManager(BaseUserManager):
    def create_user(self, phone_number=None, password=None, **extra_fields):
        if not phone_number and not extra_fields.get('email') and not extra_fields.get('google_id'):
            raise ValueError('A phone number, email, or Google account is required.')
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(phone_number, password=password, **extra_fields)


class User(UUIDModel, AbstractBaseUser, PermissionsMixin):
    phone_regex = RegexValidator(
        regex=r'^\+?[1-9]\d{7,14}$',
        message='Enter a valid phone number in international format.',
    )

    phone_number = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        validators=[phone_regex],
    )
    email = models.EmailField(max_length=254, unique=True, null=True, blank=True)
    google_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number'], name='accounts_us_phone_n_613c4a_idx'),
            models.Index(fields=['email'], name='accounts_user_email_idx'),
            models.Index(fields=['google_id'], name='accounts_user_google_idx'),
        ]

    def __str__(self):
        return self.phone_number or self.email or str(self.id)


class OTPRequest(TimeStampedModel):
    class Channel(models.TextChoices):
        SMS = 'sms', 'SMS'

    phone_number = models.CharField(max_length=20, db_index=True)
    code = models.CharField(max_length=6)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.SMS)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'OTP request'
        verbose_name_plural = 'OTP requests'
        indexes = [
            models.Index(fields=['phone_number', 'created_at']),
            models.Index(fields=['phone_number', 'is_used']),
        ]

    def __str__(self):
        return f'{self.phone_number} ({self.code})'
