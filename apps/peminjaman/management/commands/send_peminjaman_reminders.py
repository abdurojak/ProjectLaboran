from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Kompatibilitas jadwal lama; pengingat jatuh tempo dinonaktifkan.'

    def handle(self, *args, **options):
        self.stdout.write('Pengingat jatuh tempo dinonaktifkan: peminjaman tanpa batas waktu.')
