from django.core.management.base import BaseCommand

from apps.asleb.views import cleanup_expired_surat_honor


class Command(BaseCommand):
    help = 'Delete archived honor letters older than their retention period.'

    def handle(self, *args, **options):
        cleanup_expired_surat_honor()
        self.stdout.write(self.style.SUCCESS('Expired surat honor archives cleaned up.'))
