import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.common.campaigns import send_due_campaigns


class Command(BaseCommand):
    help = 'Send scheduled push notifications when they fall due. Runs until stopped.'

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=30, help='Seconds between checks.')
        parser.add_argument('--once', action='store_true', help='Check one time and exit.')

    def handle(self, *args, interval, once, **options):
        self.stdout.write(f'Push scheduler running (every {interval}s).')
        while True:
            close_old_connections()
            try:
                sent = send_due_campaigns()
                if sent:
                    self.stdout.write(f'Sent {sent} scheduled notification(s).')
            except Exception as error:  # noqa: BLE001 - keep the loop alive through a DB blip
                self.stderr.write(f'Scheduler check failed: {error}')
            if once:
                return
            time.sleep(interval)
