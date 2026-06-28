from django.core.management.base import BaseCommand

from apps.pendaftaran_asleb.services import get_current_period, sync_expired_asleb_periods


class Command(BaseCommand):
    help = 'Buat periode enam bulanan dan kembalikan role aslab yang periodenya berakhir menjadi mahasiswa.'

    def handle(self, *args, **options):
        period = get_current_period()
        expired_count, demoted_count = sync_expired_asleb_periods()
        self.stdout.write(self.style.SUCCESS(
            f'Periode aktif: {period.nama}. {expired_count} data aslab dinonaktifkan dan '
            f'{demoted_count} akun dikembalikan menjadi mahasiswa.'
        ))
