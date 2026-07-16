import os
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.core.licensing import build_license_key


class Command(BaseCommand):
    help = 'Generate a LabHub offline license key for one server fingerprint.'

    def add_arguments(self, parser):
        parser.add_argument('--customer', required=True)
        parser.add_argument('--fingerprint', required=True)
        parser.add_argument('--expires-on', required=True)

    def handle(self, *args, **options):
        signing_secret = os.getenv('LABHUB_LICENSE_SIGNING_SECRET', '').strip()
        if not signing_secret:
            raise CommandError('LABHUB_LICENSE_SIGNING_SECRET is required.')

        try:
            expires_on = date.fromisoformat(options['expires_on'])
        except ValueError as exc:
            raise CommandError('--expires-on must use YYYY-MM-DD format.') from exc

        license_key = build_license_key(
            customer=options['customer'],
            fingerprint=options['fingerprint'],
            expires_on=expires_on,
            signing_secret=signing_secret,
        )
        self.stdout.write(license_key)
