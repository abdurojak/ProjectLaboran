from datetime import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.jadwal.models import JadwalPraktikum
from apps.pengguna.models import Pengguna

from apps.asleb.forms import get_asleb_matkul
from apps.asleb.models import AbsensiAsleb, Asleb, PengingatAbsensiAsleb


class Command(BaseCommand):
    help = 'Kirim maksimal tiga pengingat email untuk jadwal praktikum yang belum diabsen aslab.'

    def handle(self, *args, **options):
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            self.stdout.write(self.style.WARNING(
                'Pengingat tidak dikirim karena EMAIL_BACKEND masih console. Konfigurasikan SMTP pada file .env.'
            ))
            return
        now = timezone.localtime()
        today = now.date()
        day_keys = [key for key, _ in JadwalPraktikum.HARI_CHOICES]
        if now.weekday() >= len(day_keys):
            self.stdout.write('Tidak ada jadwal praktikum hari ini.')
            return

        schedules = JadwalPraktikum.objects.filter(
            hari=day_keys[now.weekday()],
            status=JadwalPraktikum.STATUS_DITERIMA,
            waktu_mulai__lte=now.time().replace(tzinfo=None),
            waktu_selesai__gte=now.time().replace(tzinfo=None),
        )
        sent_count = 0
        for asleb in Asleb.objects.filter(status='aktif').exclude(email=''):
            matkul = get_asleb_matkul(asleb)
            if not matkul:
                continue
            for schedule in schedules.filter(mata_kuliah=str(matkul)):
                if AbsensiAsleb.objects.filter(asleb=asleb, jadwal=schedule, tanggal_praktikum=today).exists():
                    continue
                sent_count += self.send_next_due_reminder(asleb, schedule, now)

        self.stdout.write(self.style.SUCCESS(f'{sent_count} pengingat absensi berhasil dikirim.'))

    def send_next_due_reminder(self, asleb, schedule, now):
        start = timezone.make_aware(datetime.combine(now.date(), schedule.waktu_mulai))
        end = timezone.make_aware(datetime.combine(now.date(), schedule.waktu_selesai))
        duration = end - start
        thresholds = [start + duration * ratio for ratio in (0.25, 0.55, 0.85)]
        sent_stages = set(PengingatAbsensiAsleb.objects.filter(
            asleb=asleb,
            jadwal=schedule,
            tanggal=now.date(),
        ).values_list('tahap', flat=True))

        next_stage = next((stage for stage in range(1, 4) if stage not in sent_stages), None)
        if not next_stage or now < thresholds[next_stage - 1]:
            return 0

        recipient = asleb.email or Pengguna.objects.filter(nim_nik=asleb.nim).values_list('email', flat=True).first()
        if not recipient:
            return 0
        sent = send_mail(
            subject=f'Pengingat Absensi Aslab {next_stage}/3',
            message=(
                f'Halo {asleb.nama},\n\n'
                f'Anda belum mengisi absensi untuk {schedule.mata_kuliah} pada jadwal '
                f'{schedule.waktu_mulai:%H:%M}-{schedule.waktu_selesai:%H:%M}.\n'
                'Segera isi absensi dari lokasi praktikum sebelum jadwal berakhir. '
                'Setelah waktu selesai, absensi akan tertutup otomatis.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        if sent:
            PengingatAbsensiAsleb.objects.get_or_create(
                asleb=asleb,
                jadwal=schedule,
                tanggal=now.date(),
                tahap=next_stage,
            )
            return 1
        return 0
