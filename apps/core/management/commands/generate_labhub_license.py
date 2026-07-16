import os
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.licensing import build_license_key


class Command(BaseCommand):
    help = 'Generate a LabHub offline license key for one server fingerprint.'

    def add_arguments(self, parser):
        parser.add_argument('--customer', required=True)
        parser.add_argument('--fingerprint', required=True)
        parser.add_argument('--expires-on', required=True)

    def handle(self, *args, **options):
        private_key_file = os.getenv('LABHUB_LICENSE_PRIVATE_KEY_FILE', '').strip()
        if not private_key_file:
            raise CommandError('LABHUB_LICENSE_PRIVATE_KEY_FILE is required.')

        try:
            private_key_pem = Path(private_key_file).read_text(encoding='utf-8')
        except (OSError, UnicodeError) as exc:
            raise CommandError('Unable to read license private key file.') from exc

        try:
            expires_on = date.fromisoformat(options['expires_on'])
        except ValueError as exc:
            raise CommandError('--expires-on must use YYYY-MM-DD format.') from exc

        license_key = build_license_key(
            customer=options['customer'],
            fingerprint=options['fingerprint'],
            expires_on=expires_on,
            private_key_pem=private_key_pem,
        )
        self.stdout.write(license_key)
