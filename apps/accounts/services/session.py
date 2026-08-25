from django.db import IntegrityError

from rest_framework_simplejwt.tokens import RefreshToken

from apps.customers.models import CustomerProfile

from apps.accounts.models import User


def _split_name(first_name='', last_name='', display_name=''):
    first = (first_name or '').strip()
    last = (last_name or '').strip()
    if first or last:
        return first, last
    parts = (display_name or '').strip().split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ' '.join(parts[1:])


def _sync_profile(user):
    CustomerProfile.objects.get_or_create(
        user=user,
        defaults={'full_name': f'{user.first_name} {user.last_name}'.strip()},
    )


def _token_payload(user, created):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': user,
        'is_new_user': created,
    }


def issue_auth_payload(phone_number, first_name='', last_name=''):
    user, created = User.objects.get_or_create(
        phone_number=phone_number,
        defaults={
            'first_name': first_name,
            'last_name': last_name,
        },
    )
    if not created:
        updated = False
        for field, incoming in (('first_name', first_name), ('last_name', last_name)):
            if incoming and getattr(user, field) != incoming:
                setattr(user, field, incoming)
                updated = True
        if updated:
            user.save(update_fields=['first_name', 'last_name', 'updated_at'])

    _sync_profile(user)
    return _token_payload(user, created)


def issue_firebase_auth_payload(decoded, first_name='', last_name=''):
    phone = (decoded.get('phone_number') or '').strip() or None
    email = (decoded.get('email') or '').strip().lower() or None
    google_id = str(
        decoded.get('user_id') or decoded.get('uid') or decoded.get('sub') or ''
    ).strip() or None
    first, last = _split_name(first_name, last_name, decoded.get('name') or '')

    if phone:
        payload = issue_auth_payload(phone, first, last)
        user = payload['user']
        updated_fields = []
        if email and user.email != email:
            user.email = email
            updated_fields.append('email')
        if google_id and user.google_id != google_id:
            user.google_id = google_id
            updated_fields.append('google_id')
        if updated_fields:
            user.save(update_fields=updated_fields + ['updated_at'])
        return payload

    if not email and not google_id:
        raise ValueError('Firebase token has no email or user id.')

    return issue_google_auth_payload(
        email=email,
        google_id=google_id,
        first_name=first,
        last_name=last,
    )


def issue_google_auth_payload(email, google_id, first_name='', last_name=''):
    user = None
    if google_id:
        user = User.objects.filter(google_id=google_id).first()
    if user is None and email:
        user = User.objects.filter(email__iexact=email).first()

    created = False
    if user is None:
        user = User(
            phone_number=None,
            email=email,
            google_id=google_id,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_unusable_password()
        try:
            user.save()
            created = True
        except IntegrityError:
            if google_id:
                user = User.objects.filter(google_id=google_id).first()
            if user is None and email:
                user = User.objects.filter(email__iexact=email).first()
            if user is None:
                raise
    else:
        updated_fields = []
        if google_id and user.google_id != google_id:
            user.google_id = google_id
            updated_fields.append('google_id')
        if email and (not user.email or user.email.lower() != email):
            user.email = email
            updated_fields.append('email')
        if first_name and not user.first_name:
            user.first_name = first_name
            updated_fields.append('first_name')
        if last_name and not user.last_name:
            user.last_name = last_name
            updated_fields.append('last_name')
        if updated_fields:
            user.save(update_fields=updated_fields + ['updated_at'])

    _sync_profile(user)
    return _token_payload(user, created)
