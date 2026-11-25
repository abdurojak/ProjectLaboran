from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.emails import send_branded_email
from apps.kalender.models import EmailPerayaanTerkirim
from apps.kalender.utils import get_perayaan_items
from apps.pengguna.models import Pengguna


class Command(BaseCommand):
    help = 'Kirim ucapan email untuk perayaan kalender yang jatuh pada hari ini.'

    def handle(self, *args, **options):
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            self.stdout.write(self.style.WARNING('Email belum dikonfigurasi; ucapan tidak dikirim.'))
            return

        today = timezone.localdate()
        celebrations = [item for item in get_perayaan_items(today.year) if item['tanggal'] == today]
        sent_count = 0
        for celebration in celebrations:
            for pengguna in Pengguna.objects.filter(is_verified=True).exclude(email='').iterator():
                with transaction.atomic():
                    Pengguna.objects.select_for_update().get(pk=pengguna.pk)
                    if EmailPerayaanTerkirim.objects.filter(
                        pengguna=pengguna, tanggal=today, judul=celebration['judul'],
                    ).exists():
                        continue
                    title = celebration['judul']
                    greeting = f'Halo {pengguna.nama_pengguna},'
                    if title == 'Peringatan Tragedi Trisakti':
                        subject = 'Mengenang Tragedi Trisakti bersama LabHub'
                        headline = 'Mengenang Tragedi Trisakti'
                        intro = 'Hari ini kita mengenang para korban Tragedi Trisakti. Semoga semangat perjuangan, kepedulian, dan kemanusiaan terus hidup dalam langkah kita.'
                    else:
                        subject = f'Selamat {title} dari LabHub'
                        headline = f'Selamat {title}!'
                        intro = (
                            f'Selamat {title}! Semoga semangat dan nilai baik dari hari ini '
                            'terus menginspirasi langkah kita bersama. Salam hangat dari LabHub.'
                        )
                    sent = send_branded_email(
                        subject=subject,
                        recipients=[pengguna.email],
                        text_body=f'{greeting}\n\n{intro}',
                        title=headline,
                        greeting=greeting,
                        intro=intro,
                        eyebrow='Ucapan LabHub',
                        details=[{'label': 'Hari peringatan', 'value': today.strftime('%d-%m-%Y')}],
                    )
                    if sent:
                        EmailPerayaanTerkirim.objects.create(
                            pengguna=pengguna, tanggal=today, judul=title,
                        )
                        sent_count += 1
        self.stdout.write(self.style.SUCCESS(f'{sent_count} ucapan perayaan berhasil dikirim.'))
