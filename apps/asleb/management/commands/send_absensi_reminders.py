from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.emails import send_branded_email
from apps.jadwal.models import JadwalPraktikum
from apps.pengguna.models import Pengguna

from apps.asleb.models import Asleb, PengingatAbsensiAsleb
from apps.asleb.services import get_asleb_schedule_queryset, get_attendance_source_for_slot


class Command(BaseCommand):
    help = 'Kirim pengingat email setiap empat jam selama hari jadwal jika aslab belum absen.'

    def handle(self, *args, **options):
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            self.stdout.write(self.style.WARNING(
                'Pengingat tidak dikirim karena EMAIL_BACKEND masih console. Konfigurasikan SMTP pada file .env.'
            ))
            return

        now = timezone.localtime()
        day_keys = [key for key, _ in JadwalPraktikum.HARI_CHOICES]
        if now.weekday() >= len(day_keys):
            self.stdout.write('Tidak ada jadwal praktikum hari ini.')
            return

        schedules = JadwalPraktikum.objects.filter(
            hari=day_keys[now.weekday()],
            status=JadwalPraktikum.STATUS_DITERIMA,
            waktu_mulai__lte=now.time().replace(tzinfo=None),
        )
        sent_count = 0
        for asleb in Asleb.objects.filter(status='aktif'):
            owned_schedule_ids = get_asleb_schedule_queryset(
                asleb, statuses=[JadwalPraktikum.STATUS_DITERIMA],
            ).values('pk')
            for schedule in schedules.filter(pk__in=owned_schedule_ids):
                sent_count += self.send_next_due_reminder(asleb, schedule, now)

        self.stdout.write(self.style.SUCCESS(f'{sent_count} pengingat absensi berhasil dikirim.'))

    @transaction.atomic
    def send_next_due_reminder(self, asleb, schedule, now):
        asleb = Asleb.objects.select_for_update().get(pk=asleb.pk)
        today = now.date()
        if get_attendance_source_for_slot(asleb, schedule, today):
            return 0

        start = timezone.make_aware(datetime.combine(today, schedule.waktu_mulai))
        reminders = PengingatAbsensiAsleb.objects.filter(
            asleb=asleb, jadwal=schedule, tanggal=today,
        )
        latest = reminders.order_by('-dikirim_pada').first()
        if now < start or (latest and now < timezone.localtime(latest.dikirim_pada) + timedelta(hours=4)):
            return 0

        recipient = Pengguna.objects.filter(
            nim_nik=asleb.nim, role='asisten_lab', is_verified=True,
        ).exclude(email='').values_list('email', flat=True).first() or asleb.email
        if not recipient:
            return 0

        stage = (reminders.order_by('-tahap').values_list('tahap', flat=True).first() or 0) + 1
        attendance_url = f"{settings.PUBLIC_ACCESS_BASE_URL.rstrip('/')}/asleb/absensi/tambah/"
        text_body = (
            f'Halo {asleb.nama},\n\n'
            f'Absensi {schedule.mata_kuliah} untuk jadwal hari ini '
            f'{schedule.waktu_mulai:%H:%M}-{schedule.waktu_selesai:%H:%M} belum tercatat.\n'
            'Jika waktu absensi sudah ditutup, hubungi laboran untuk meminta izin absensi susulan.'
        )
        sent = send_branded_email(
            subject='Pengingat Absensi Aslab Hari Ini',
            recipients=[recipient],
            text_body=text_body,
            title='Absensi hari ini belum tercatat',
            greeting=f'Halo {asleb.nama},',
            intro='Jadwal praktikum Anda hari ini belum memiliki catatan absensi.',
            details=[
                {'label': 'Mata kuliah', 'value': schedule.mata_kuliah},
                {'label': 'Ruangan', 'value': schedule.get_display_ruangan_nama()},
                {'label': 'Waktu', 'value': f'{schedule.waktu_mulai:%H:%M} - {schedule.waktu_selesai:%H:%M}'},
                {'label': 'Tanggal', 'value': today.strftime('%d-%m-%Y')},
            ],
            action_url=attendance_url,
            action_label='Lihat Absensi',
            note='Jika jadwal sudah berakhir, minta laboran membuka izin absensi susulan. Pengingat berhenti setelah absensi tercatat.',
            fail_silently=False,
        )
        if not sent:
            return 0
        PengingatAbsensiAsleb.objects.create(
            asleb=asleb, jadwal=schedule, tanggal=today, tahap=stage,
        )
        return 1
