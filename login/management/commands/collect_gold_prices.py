"""Run once from a cron job, or continuously as a dedicated worker."""
import threading

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from login.gold import collect_gold_quote


class Command(BaseCommand):
    help = 'Collect INR gold prices for 24-hour comparisons, without dashboard visits.'

    def add_arguments(self, parser):
        parser.add_argument('--continuous', action='store_true', help='Poll every minute until stopped.')

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            try:
                collected = collect_gold_quote()
                if not options['continuous']:
                    self.stdout.write('Gold quote collected.' if collected else 'Gold collection already claimed by another worker.')
            except Exception as exc:
                if not options['continuous']:
                    raise CommandError('Gold collection failed; check connectivity and retry.') from exc
                self.stderr.write('Gold collection failed; retrying in one minute.')
            finally:
                close_old_connections()
            if not options['continuous']:
                return
            try:
                threading.Event().wait(60)
            except KeyboardInterrupt:
                return
