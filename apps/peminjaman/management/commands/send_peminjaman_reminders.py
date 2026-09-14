from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.peminjaman.models import PengingatPeminjaman, PeminjamanTransaksi
from apps.peminjaman.notifications import send_due_reminder_notification


class Command(BaseCommand):
    help = 'Kirim pengingat jatuh tempo dan keterlambatan peminjaman, maksimal sekali per hari.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        reminder_limit = today + timedelta(days=1)
        transactions = (
            PeminjamanTransaksi.objects.filter(
                detail__status='dipinjam',
                tanggal_kembali__lte=reminder_limit,
            )
            .exclude(nim='')
            .prefetch_related('detail')
            .distinct()
        )
        sent_count = 0
        for transaksi in transactions:
            overdue = transaksi.tanggal_kembali < today
            reminder_type = 'terlambat' if overdue else 'jatuh_tempo'
            reminder, created = PengingatPeminjaman.objects.get_or_create(
                transaksi=transaksi,
                tanggal=today,
                jenis=reminder_type,
            )
            if not created:
                continue
            if send_due_reminder_notification(transaksi, overdue=overdue):
                sent_count += 1
            else:
                reminder.delete()

        self.stdout.write(self.style.SUCCESS(f'{sent_count} pengingat peminjaman berhasil dikirim.'))
