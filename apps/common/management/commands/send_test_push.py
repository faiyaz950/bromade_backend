from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.accounts.models import User, UserDeviceToken
from apps.common.push import deliver_now, push_enabled


class Command(BaseCommand):
    help = 'Send a test push to every phone a customer is signed in on.'

    def add_arguments(self, parser):
        parser.add_argument('user', help='Phone number (+91…) or email of the customer.')

    def handle(self, *args, user, **options):
        if not push_enabled():
            raise CommandError(
                'Push is off: set FIREBASE_SERVICE_ACCOUNT_FILE or FIREBASE_SERVICE_ACCOUNT_JSON.'
            )
        account = User.objects.filter(Q(phone_number=user) | Q(email__iexact=user)).first()
        if account is None:
            raise CommandError(f'No user with phone or email "{user}".')
        tokens = list(UserDeviceToken.objects.filter(user=account).values_list('token', flat=True))
        if not tokens:
            raise CommandError('This user has no registered phones. Open the app signed in, then retry.')

        # Sent inline (not via send_push's background thread) so we can report back.
        report = deliver_now(tokens, 'Demess test notification', 'Push notifications are working.')
        self.stdout.write(self.style.SUCCESS(f'Sent to {report.delivered} of {len(tokens)} phone(s).'))
        if report.expired:
            self.stdout.write(f'Removed {report.expired} expired token(s).')
