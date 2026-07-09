from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.asleb.models import AbsensiAsleb, Asleb, HonorAsleb, HasilPraktikumMahasiswa, ModulPraktikum, PesertaPraktikum
from apps.inventaris.models import ACTIVE_PEMINJAMAN_STATUSES, Barang, InventarisBarang
from apps.jadwal.models import JadwalPraktikum
from apps.jadwal.notifications import send_jadwal_status_notification
from apps.kalender.realtime import (
    send_peminjaman_rejected_update,
    send_peminjaman_status_update,
    send_schedule_update,
)
from apps.kalender.models import KegiatanKalender, Notifikasi
from apps.core.permissions import LABORAN_ROLE, can_manage_lab_operations
from apps.peminjaman.models import PeminjamanAlat
from apps.peminjaman.notifications import send_peminjaman_status_notification
from apps.pendaftaran_asleb.models import MataKuliahAsleb, PendaftaranAsleb, PengaturanPendaftaranAsleb, RiwayatAsleb
from apps.pendaftaran_asleb.services import is_registration_open
from apps.pendaftaran_asleb.utils import get_public_registration_url


class DashboardView(TemplateView):
    template_name = 'dashboard/home.html'
    WEEKDAY_TO_HARI = {
        0: 'senin',
        1: 'selasa',
        2: 'rabu',
        3: 'kamis',
        4: 'jumat',
        5: 'sabtu',
    }

    TONES = {
        'teal': {
            'icon_bg': 'bg-cyan-50',
            'icon_text': 'text-cyan-700',
            'value_text': 'text-cyan-700',
        },
        'orange': {
            'icon_bg': 'bg-amber-50',
            'icon_text': 'text-amber-600',
            'value_text': 'text-amber-600',
        },
        'blue': {
            'icon_bg': 'bg-blue-50',
            'icon_text': 'text-blue-700',
            'value_text': 'text-blue-700',
        },
        'purple': {
            'icon_bg': 'bg-violet-50',
            'icon_text': 'text-violet-700',
            'value_text': 'text-violet-700',
        },
        'green': {
            'icon_bg': 'bg-emerald-50',
            'icon_text': 'text-emerald-700',
            'value_text': 'text-emerald-700',
        },
        'gray': {
            'icon_bg': 'bg-slate-100',
            'icon_text': 'text-slate-500',
            'value_text': 'text-slate-700',
        },
    }

    def _decorate_items(self, items):
        for item in items:
            tone = self.TONES.get(item['tone'], self.TONES['gray'])
            item.update(tone)
        return items

    def format_rupiah(self, value):
        return f'Rp {value:,.0f}'.replace(',', '.')

    def get_asisten_lab_matkul_labels(self, pengguna):
        if not pengguna or pengguna.role != 'asisten_lab':
            return []

        matkul_values = PendaftaranAsleb.objects.filter(
            nim=pengguna.nim_nik,
            status__in=['diterima', 'digenerate'],
        ).select_related('matkul').values_list(
            'matkul__nama',
            'matkul__dosen',
            'matkul__kelas',
        )
        labels = [f'{nama} - {dosen} - {kelas}' for nama, dosen, kelas in matkul_values]

        history_values = RiwayatAsleb.objects.filter(nim=pengguna.nim_nik).values_list(
            'matkul__nama',
            'matkul__dosen',
            'matkul__kelas',
        )
        labels.extend(f'{nama} - {dosen} - {kelas}' for nama, dosen, kelas in history_values)

        labels.extend(
            Asleb.objects.filter(nim=pengguna.nim_nik, status='aktif')
            .exclude(matkul='')
            .values_list('matkul', flat=True)
        )
        return list(dict.fromkeys(labels))

    def get_grouped_peminjaman(self, queryset, limit=6):
        grouped = []
        seen_keys = set()
        for peminjaman in queryset.select_related('barang', 'transaksi').order_by('-tanggal_pinjam', '-dibuat_pada'):
            key = peminjaman.transaksi_id or peminjaman.kode_pinjam or f'row-{peminjaman.pk}'
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if peminjaman.transaksi_id:
                detail_count = PeminjamanAlat.objects.filter(transaksi_id=peminjaman.transaksi_id).count()
            else:
                detail_count = PeminjamanAlat.objects.filter(kode_pinjam=peminjaman.kode_pinjam).count()
            peminjaman.jumlah_barang_transaksi = detail_count
            grouped.append(peminjaman)
            if len(grouped) >= limit:
                break
        return grouped

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = getattr(self.request, 'current_pengguna', None)
        inventaris_qs = InventarisBarang.objects.all()
        barang_qs = Barang.objects.all()
        jadwal_qs = JadwalPraktikum.objects.all()
        kegiatan_qs = KegiatanKalender.objects.all()
        peminjaman_qs = PeminjamanAlat.objects.select_related('barang')
        peminjaman_aktif = peminjaman_qs.filter(status__in=ACTIVE_PEMINJAMAN_STATUSES)
        asleb_qs = Asleb.objects.all()
        pendaftaran_asleb_qs = PendaftaranAsleb.objects.all()
        is_mahasiswa = bool(pengguna and pengguna.role == 'mahasiswa')
        is_asisten_lab = bool(pengguna and pengguna.role == 'asisten_lab')
        context['is_mahasiswa_dashboard'] = is_mahasiswa or is_asisten_lab
        context['is_asisten_lab_dashboard'] = is_asisten_lab
        context['is_manager_dashboard'] = bool(pengguna and pengguna.role == LABORAN_ROLE)

        if context['is_mahasiswa_dashboard']:
            pengaturan_pendaftaran = PengaturanPendaftaranAsleb.get_solo()
            peminjaman_saya = peminjaman_qs.filter(nim=pengguna.nim_nik)
            today = timezone.localdate()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            peminjaman_bermasalah = peminjaman_saya.filter(
                status__in=['dipinjam', 'rusak', 'hilang'],
            ).filter(
                Q(status__in=['rusak', 'hilang']) | Q(status='dipinjam', tanggal_kembali__lt=today),
            ).order_by('tanggal_kembali', '-diperbarui_pada')
            peringatan_peminjaman_saya = []
            for peminjaman in peminjaman_bermasalah[:5]:
                if peminjaman.status == 'dipinjam':
                    label = 'Lewat masa pengembalian'
                    tone = 'amber'
                else:
                    label = peminjaman.get_status_display()
                    tone = 'rose' if peminjaman.status == 'hilang' else 'orange'
                peringatan_peminjaman_saya.append({
                    'barang': peminjaman.barang.nama,
                    'label': label,
                    'tanggal_kembali': peminjaman.tanggal_kembali,
                    'url': reverse('peminjaman:peminjaman_detail', kwargs={'pk': peminjaman.pk}),
                    'tone': tone,
                })
            awal_bulan = timezone.localdate().replace(day=1)
            honor_bulan_ini = HonorAsleb.objects.filter(
                asleb__nim=pengguna.nim_nik,
                bulan__year=awal_bulan.year,
                bulan__month=awal_bulan.month,
            ).exclude(status='dibayar').aggregate(total=Sum('jumlah'))['total'] or 0
            riwayat_honor_saya = HonorAsleb.objects.filter(
                asleb__nim=pengguna.nim_nik,
            ).select_related('asleb')[:6]
            for honor in riwayat_honor_saya:
                honor.bukti_pendukung_list = list(
                    AbsensiAsleb.objects.filter(
                        asleb=honor.asleb,
                        tanggal_praktikum__year=honor.bulan.year,
                        tanggal_praktikum__month=honor.bulan.month,
                    ).order_by('-tanggal_praktikum')[:3]
                )
            context['today'] = timezone.localdate()
            hari_ini = self.WEEKDAY_TO_HARI.get(context['today'].weekday())
            context['peminjaman_saya'] = peminjaman_saya[:6]
            context['peringatan_peminjaman_saya'] = peringatan_peminjaman_saya
            context['has_peringatan_peminjaman_saya'] = bool(peringatan_peminjaman_saya)
            context['riwayat_honor_saya'] = riwayat_honor_saya
            peserta_praktikum = (
                PesertaPraktikum.objects
                .select_related('matkul')
                .filter(Q(pengguna=pengguna) | Q(nim=pengguna.nim_nik), aktif=True)
            )
            mahasiswa_matkul_ids = list(peserta_praktikum.values_list('matkul_id', flat=True).distinct())
            mahasiswa_matkul_labels = [str(peserta.matkul) for peserta in peserta_praktikum]
            asisten_matkul_ids = []
            matkul_labels = []
            if is_asisten_lab:
                matkul_labels = self.get_asisten_lab_matkul_labels(pengguna)
                asisten_matkul_ids = list(
                    MataKuliahAsleb.objects.filter(
                        Q(pendaftaran__nim=pengguna.nim_nik, pendaftaran__status__in=['diterima', 'digenerate'])
                        | Q(riwayat_asleb__nim=pengguna.nim_nik)
                        | Q(nama__in=[label.split(' - ')[0] for label in matkul_labels])
                    ).values_list('pk', flat=True).distinct()
                )

            allowed_labels = matkul_labels if is_asisten_lab else mahasiswa_matkul_labels
            allowed_matkul_ids = asisten_matkul_ids if is_asisten_lab else mahasiswa_matkul_ids

            jadwal_hari_ini = jadwal_qs.filter(
                hari=hari_ini,
                status=JadwalPraktikum.STATUS_DITERIMA,
            ) if hari_ini else jadwal_qs.none()
            if allowed_labels:
                jadwal_hari_ini = jadwal_hari_ini.filter(mata_kuliah__in=allowed_labels)
            elif is_asisten_lab or is_mahasiswa:
                jadwal_hari_ini = jadwal_qs.none()

            jadwal_minggu_ini = jadwal_qs.filter(status=JadwalPraktikum.STATUS_DITERIMA)
            if allowed_labels:
                jadwal_minggu_ini = jadwal_minggu_ini.filter(mata_kuliah__in=allowed_labels)
            else:
                jadwal_minggu_ini = jadwal_qs.none()

            modul_tersedia = ModulPraktikum.objects.select_related('matkul').filter(matkul_id__in=allowed_matkul_ids)
            hasil_absensi_saya = HasilPraktikumMahasiswa.objects.filter(peserta__in=peserta_praktikum) if not is_asisten_lab else HasilPraktikumMahasiswa.objects.filter(modul__matkul_id__in=allowed_matkul_ids)
            notifikasi_saya = Notifikasi.objects.filter(pengguna=pengguna).order_by('-source_updated_at', '-id')

            context['jadwal_hari_ini'] = jadwal_hari_ini[:6]
            context['pendaftaran_asleb_dibuka'] = is_mahasiswa and is_registration_open()
            context['kegiatan_kalender_mahasiswa'] = kegiatan_qs.filter(tanggal__gte=context['today'])[:6]
            context['public_registration_url'] = get_public_registration_url()
            if is_asisten_lab:
                stats_cards = [
                    {
                        'label': 'Jadwal Mengajar',
                        'value': jadwal_minggu_ini.count(),
                        'note': 'Jadwal praktikum aktif minggu ini',
                        'icon': 'calendar-clock',
                        'tone': 'blue',
                    },
                    {
                        'label': 'Praktikum Hari Ini',
                        'value': jadwal_hari_ini.count(),
                        'note': 'Yang perlu didampingi hari ini',
                        'icon': 'monitor-check',
                        'tone': 'teal',
                    },
                    {
                        'label': 'Kelas Diampu',
                        'value': len(allowed_matkul_ids),
                        'note': 'Mata kuliah/kelas aktif',
                        'icon': 'presentation',
                        'tone': 'green',
                    },
                    {
                        'label': 'Absensi Tercatat',
                        'value': hasil_absensi_saya.count(),
                        'note': 'Data nilai/absensi mahasiswa terkait',
                        'icon': 'clipboard-check',
                        'tone': 'purple',
                    },
                ]
            else:
                stats_cards = [
                    {
                        'label': 'Jadwal Minggu Ini',
                        'value': jadwal_minggu_ini.count(),
                        'note': 'Praktikum sesuai mata kuliah Anda',
                        'icon': 'calendar-days',
                        'tone': 'blue',
                    },
                    {
                        'label': 'Praktikum Hari Ini',
                        'value': jadwal_hari_ini.count(),
                        'note': 'Jadwal yang berlangsung hari ini',
                        'icon': 'book-open-check',
                        'tone': 'teal',
                    },
                    {
                        'label': 'Modul Tersedia',
                        'value': modul_tersedia.count(),
                        'note': 'Modul dari kelas praktikum Anda',
                        'icon': 'files',
                        'tone': 'green',
                    },
                    {
                        'label': 'Notifikasi Baru',
                        'value': notifikasi_saya.filter(dibaca_pada__isnull=True).count(),
                        'note': 'Pemberitahuan yang belum dibaca',
                        'icon': 'bell-ring',
                        'tone': 'purple',
                    },
                ]

            context['stats_cards'] = self._decorate_items(stats_cards)
            context['dashboard_user_name'] = (pengguna.nama_pengguna or 'Teman').split()[0]
            context['jadwal_minggu_ini'] = jadwal_minggu_ini[:5]
            context['modul_terbaru'] = modul_tersedia.order_by('-dibuat_pada')[:5]
            context['notifikasi_terbaru'] = notifikasi_saya[:5]
            context['hasil_absensi_terbaru'] = hasil_absensi_saya.select_related('modul', 'peserta').order_by('-tanggal_praktikum', '-diperbarui_pada')[:5]
            menu_modules = [
                {
                    'title': 'Peminjaman Alat',
                    'description': 'Ajukan peminjaman alat dan pantau status pengajuan Anda.',
                    'url': 'peminjaman:peminjaman_list',
                    'status': 'Aktif',
                    'icon': 'arrow-left-right',
                    'tone': 'orange',
                },
                {
                    'title': 'Jadwal Praktikum',
                    'description': 'Lihat jadwal praktikum yang terdaftar di laboratorium.',
                    'url': 'jadwal:jadwal_list',
                    'status': 'Aktif',
                    'icon': 'calendar-days',
                    'tone': 'blue',
                },
            ]

            if is_asisten_lab:
                menu_modules.extend([
                    {
                        'title': 'Absensi Aslab',
                        'description': 'Isi absensi praktikum, upload modul, dan bukti video kegiatan.',
                        'url': 'asleb:absensi_list',
                        'status': 'Aktif',
                        'icon': 'clipboard-check',
                        'tone': 'teal',
                    },
                    {
                        'title': 'Kalender',
                        'description': 'Lihat agenda kegiatan laboratorium dan notifikasi yang relevan.',
                        'url': 'kalender:kegiatan_list',
                        'status': 'Aktif',
                        'icon': 'calendar-range',
                        'tone': 'purple',
                    },
                    {
                        'title': 'Ruangan',
                        'description': 'Lihat daftar ruangan laboratorium dan kapasitasnya.',
                        'url': 'ruangan:ruangan_list',
                        'status': 'Aktif',
                        'icon': 'door-open',
                        'tone': 'green',
                    },
                ])
            else:
                menu_modules.append({
                    'title': 'Ruangan',
                    'description': 'Lihat daftar lab dan informasi ruangan yang tersedia.',
                    'url': 'ruangan:ruangan_list',
                    'status': 'Aktif',
                    'icon': 'door-open',
                    'tone': 'orange',
                })

            context['menu_modules'] = self._decorate_items(menu_modules)
            return context

        context['total_barang'] = inventaris_qs.count()
        context['total_unit'] = inventaris_qs.aggregate(total=Sum('jumlah'))['total'] or 0
        context['kondisi_baik'] = barang_qs.filter(kondisi='baik').count()
        context['butuh_perhatian'] = barang_qs.exclude(kondisi='baik').count()
        context['barang_terbaru'] = inventaris_qs.order_by('-dibuat_pada')[:5]
        context['peminjaman_terbaru'] = peminjaman_qs[:5]
        context['peminjaman_diajukan'] = self.get_grouped_peminjaman(peminjaman_qs.filter(status='diajukan'))
        context['peminjaman_dipinjam'] = self.get_grouped_peminjaman(peminjaman_qs.filter(status='dipinjam'))
        context['peminjaman_perlu_diganti'] = self.get_grouped_peminjaman(peminjaman_qs.filter(status__in=['hilang', 'rusak']))
        context['jadwal_diajukan'] = JadwalPraktikum.objects.select_related('ruangan').filter(
            status=JadwalPraktikum.STATUS_DIAJUKAN,
        ).order_by('hari', 'waktu_mulai')[:8]
        context['today'] = timezone.localdate()
        hari_ini = self.WEEKDAY_TO_HARI.get(context['today'].weekday())
        context['stats_cards'] = self._decorate_items([
            {
                'label': 'Total Barang',
                'value': context['total_barang'],
                'note': 'Semua barang terdaftar',
                'icon': 'package',
                'tone': 'teal',
            },
            {
                'label': 'Menunggu Peminjaman',
                'value': peminjaman_qs.filter(status='diajukan').count(),
                'note': 'Pengajuan yang perlu diproses',
                'icon': 'arrow-left-right',
                'tone': 'orange',
            },
            {
                'label': 'Menunggu Jadwal',
                'value': context['jadwal_diajukan'].count(),
                'note': 'Jadwal yang perlu ditinjau',
                'icon': 'calendar-clock',
                'tone': 'blue',
            },
            {
                'label': 'Calon Aslab',
                'value': pendaftaran_asleb_qs.filter(status='diajukan').count(),
                'note': 'Pendaftar yang perlu diseleksi',
                'icon': 'user-round-check',
                'tone': 'green',
            },
        ])
        context['menu_modules'] = self._decorate_items([
            {
                'title': 'Inventaris',
                'description': 'Kelola data barang, kondisi, dan lokasi penyimpanan alat laboratorium.',
                'url': 'inventaris:barang_list',
                'status': 'Aktif',
                'icon': 'package',
                'tone': 'teal',
            },
            {
                'title': 'Peminjaman Alat',
                'description': 'Catat peminjaman dan pengembalian alat laboratorium dari satu modul terpusat.',
                'url': 'peminjaman:peminjaman_list',
                'status': 'Aktif',
                'icon': 'arrow-left-right',
                'tone': 'orange',
            },
            {
                'title': 'Jadwal Praktikum',
                'description': 'Kelola jadwal praktikum sebagai modul tersendiri, terpisah dari kalender kegiatan umum.',
                'url': 'jadwal:jadwal_list',
                'status': 'Aktif',
                'icon': 'calendar-days',
                'tone': 'blue',
            },
            {
                'title': 'Data Aslab',
                'description': 'Kelola data asisten laboratorium untuk membantu operasional praktikum.',
                'url': 'asleb:asleb_list',
                'status': 'Aktif',
                'icon': 'users',
                'tone': 'green',
            },
            {
                'title': 'Pendaftaran Aslab',
                'description': 'Kelola calon aslab yang mendaftar berdasarkan matkul, kontak, dan status seleksi.',
                'url': 'pendaftaran_asleb:pendaftaran_list',
                'status': 'Aktif',
                'icon': 'user-round-plus',
                'tone': 'teal',
            },
            {
                'title': 'Rekap Honorarium Aslab',
                'description': 'Hitung honor aslab per bulan berdasarkan total pertemuan, batas 60 jam, dan tarif Junior/Senior.',
                'url': 'asleb:honor_list',
                'status': 'Aktif',
                'icon': 'file-chart-column',
                'tone': 'purple',
            },
            {
                'title': 'Pengguna',
                'description': 'Kelola akun dan hak akses sistem setelah modul inventaris stabil.',
                'url': '',
                'status': 'Segera Hadir',
                'icon': 'user-round',
                'tone': 'teal',
            },
            {
                'title': 'Ruangan',
                'description': 'Akses daftar lab seperti RPL, SKI, Pemrograman, SDA, dan Rekayasa Data.',
                'url': 'ruangan:ruangan_list',
                'status': 'Aktif',
                'icon': 'door-open',
                'tone': 'orange',
            },
            {
                'title': 'Pengaturan',
                'description': 'Konfigurasi sistem dan preferensi laboratorium akan menyusul.',
                'url': '',
                'status': 'Segera Hadir',
                'icon': 'settings',
                'tone': 'gray',
            },
        ])
        context['activities'] = [
            {
                'time': '10:15',
                'title': 'Barang baru ditambahkan',
                'detail': 'Data inventaris terbaru akan muncul di sini setelah modul inventaris dipakai.',
                'tone': 'teal',
            },
            {
                'time': '09:47',
                'title': 'Peminjaman alat dibuat',
                'detail': 'Transaksi peminjaman baru sekarang bisa dicatat dari modul peminjaman alat.',
                'tone': 'orange',
            },
            {
                'time': '09:30',
                'title': 'Jadwal praktikum dibuat',
                'detail': 'Jadwal praktikum sekarang punya modul sendiri dan tidak bercampur lagi dengan kalender umum.',
                'tone': 'blue',
            },
            {
                'time': '08:55',
                'title': 'Data aslab diperbarui',
                'detail': f'{asleb_qs.filter(status="aktif").count()} aslab aktif dan {pendaftaran_asleb_qs.filter(status="diajukan").count()} pendaftar menunggu seleksi.',
                'tone': 'green',
            },
        ]
        context['quick_actions'] = self._decorate_items([
            {
                'title': 'Tambah Barang Baru',
                'description': 'Tambahkan data inventaris baru ke sistem.',
                'url': 'inventaris:barang_create',
                'icon': 'plus',
                'tone': 'teal',
            },
            {
                'title': 'Lihat Daftar Inventaris',
                'description': 'Buka seluruh data barang laboratorium.',
                'url': 'inventaris:barang_list',
                'icon': 'package',
                'tone': 'orange',
            },
            {
                'title': 'Barang Mahasiswa Tertinggal',
                'description': 'Buka halaman pendataan barang mahasiswa yang tertinggal di laboratorium.',
                'url': 'barang_tertinggal:list',
                'icon': 'briefcase',
                'tone': 'teal',
            },
            {
                'title': 'Buat Peminjaman Alat',
                'description': 'Catat transaksi peminjaman alat laboratorium baru.',
                'url': 'peminjaman:peminjaman_create',
                'icon': 'handshake',
                'tone': 'blue',
            },
            {
                'title': 'Tambah Jadwal Praktikum',
                'description': 'Masukkan jadwal praktikum baru ke modul jadwal.',
                'url': 'jadwal:jadwal_create',
                'icon': 'calendar-plus-2',
                'tone': 'blue',
            },
            {
                'title': 'Tambah Data Aslab',
                'description': 'Masukkan data asisten laboratorium baru.',
                'url': 'asleb:asleb_create',
                'icon': 'user-plus',
                'tone': 'green',
            },
            {
                'title': 'Tambah Pendaftaran Aslab',
                'description': 'Catat calon aslab baru beserta matkul yang diminati.',
                'url': 'pendaftaran_asleb:pendaftaran_create',
                'icon': 'user-round-plus',
                'tone': 'teal',
            },
            {
                'title': 'Tambah Kegiatan Kalender',
                'description': 'Catat kegiatan umum dan tandai untuk notifikasi bila diperlukan.',
                'url': 'kalender:kegiatan_create',
                'icon': 'calendar-range',
                'tone': 'purple',
            },
            {
                'title': 'Lihat Daftar Peminjaman',
                'description': 'Pantau status pinjam, kembali, dan transaksi aktif.',
                'url': 'peminjaman:peminjaman_list',
                'icon': 'clipboard-list',
                'tone': 'purple',
            },
        ])
        return context


@require_POST
def accept_peminjaman(request, pk):
    if not _is_admin_or_laboran(request):
        messages.warning(request, 'Anda tidak memiliki akses untuk memproses peminjaman.')
        return redirect('dashboard:home')

    with transaction.atomic():
        peminjaman = get_object_or_404(
            PeminjamanAlat.objects.select_for_update().select_related('barang', 'transaksi'),
            pk=pk,
        )
        group = _get_peminjaman_group_for_update(peminjaman)

        if any(item.status != 'diajukan' for item in group):
            messages.warning(request, 'Pengajuan ini sudah diproses.')
            return redirect('dashboard:home')

        for item in group:
            barang = Barang.objects.select_for_update().get(pk=item.barang_id)
            if barang.sedang_dipinjam:
                messages.error(request, f'{barang.nama} sedang dipinjam.')
                return redirect('dashboard:home')

        for item in group:
            item.status = 'dipinjam'
            item.save(update_fields=['status', 'diperbarui_pada'])
            send_peminjaman_status_notification(item)
            transaction.on_commit(lambda item_id=item.pk: send_peminjaman_status_update(
                PeminjamanAlat.objects.select_related('barang').get(pk=item_id)
            ))
        messages.success(request, 'Pengajuan peminjaman diterima.')

    return redirect('dashboard:home')


@require_POST
def reject_peminjaman(request, pk):
    if not _is_admin_or_laboran(request):
        messages.warning(request, 'Anda tidak memiliki akses untuk memproses peminjaman.')
        return redirect('dashboard:home')

    with transaction.atomic():
        peminjaman = get_object_or_404(
            PeminjamanAlat.objects.select_for_update().select_related('barang', 'transaksi'),
            pk=pk,
            status='diajukan',
        )
        group = _get_peminjaman_group_for_update(peminjaman)
        if any(item.status != 'diajukan' for item in group):
            messages.warning(request, 'Pengajuan ini sudah diproses.')
            return redirect('dashboard:home')

        transaksi = peminjaman.transaksi
        rejected_items = list(group.select_related('barang'))
        group.delete()
        if transaksi and not transaksi.detail.exists():
            transaksi.delete()

        for item in rejected_items:
            transaction.on_commit(lambda rejected=item: send_peminjaman_rejected_update(rejected))

    messages.success(request, 'Pengajuan peminjaman ditolak dan dihapus dari daftar.')
    return redirect('dashboard:home')


def _is_admin_or_laboran(request):
    pengguna = getattr(request, 'current_pengguna', None)
    return can_manage_lab_operations(pengguna)


@require_POST
def accept_jadwal(request, pk):
    if not _is_admin_or_laboran(request):
        messages.warning(request, 'Anda tidak memiliki akses untuk memproses pengajuan jadwal.')
        return redirect('dashboard:home')

    jadwal = get_object_or_404(JadwalPraktikum.objects.select_related('ruangan'), pk=pk, status=JadwalPraktikum.STATUS_DIAJUKAN)
    jadwal.status = JadwalPraktikum.STATUS_DITERIMA

    try:
        jadwal.full_clean()
    except ValidationError:
        messages.error(
            request,
            'Jadwal tidak bisa diterima karena ruangan sudah dipakai pada hari dan rentang waktu tersebut.',
        )
        return redirect('dashboard:home')

    jadwal.save(update_fields=['status', 'diperbarui_pada'])
    send_jadwal_status_notification(jadwal)
    transaction.on_commit(lambda: send_schedule_update(jadwal, event='schedule.accepted'))
    messages.success(request, 'Pengajuan jadwal praktikum diterima.')
    return redirect('dashboard:home')


@require_POST
def reject_jadwal(request, pk):
    if not _is_admin_or_laboran(request):
        messages.warning(request, 'Anda tidak memiliki akses untuk memproses pengajuan jadwal.')
        return redirect('dashboard:home')

    jadwal = get_object_or_404(JadwalPraktikum, pk=pk, status=JadwalPraktikum.STATUS_DIAJUKAN)
    jadwal.status = JadwalPraktikum.STATUS_DITOLAK
    jadwal.save(update_fields=['status', 'diperbarui_pada'])
    send_jadwal_status_notification(jadwal)
    transaction.on_commit(lambda: send_schedule_update(jadwal, event='schedule.rejected'))
    messages.success(request, 'Pengajuan jadwal praktikum ditolak.')
    return redirect('dashboard:home')


def _mark_borrowed_status(request, pk, status):
    if not _is_admin_or_laboran(request):
        messages.warning(request, 'Anda tidak memiliki akses untuk mengubah status peminjaman.')
        return redirect('dashboard:home')

    with transaction.atomic():
        peminjaman = get_object_or_404(PeminjamanAlat.objects.select_for_update(), pk=pk, status='dipinjam')
        for item in _get_peminjaman_group_for_update(peminjaman).filter(status='dipinjam'):
            item.status = status
            item.save(update_fields=['status', 'diperbarui_pada'])
            send_peminjaman_status_notification(item)
    return redirect('dashboard:home')


@require_POST
def mark_peminjaman_returned(request, pk):
    return _mark_borrowed_status(request, pk, 'dikembalikan')


@require_POST
def mark_peminjaman_lost(request, pk):
    return _mark_borrowed_status(request, pk, 'hilang')


@require_POST
def mark_peminjaman_broken(request, pk):
    return _mark_borrowed_status(request, pk, 'rusak')


@require_POST
def mark_peminjaman_replaced(request, pk):
    if not _is_admin_or_laboran(request):
        messages.warning(request, 'Anda tidak memiliki akses untuk mengubah status peminjaman.')
        return redirect('dashboard:home')

    with transaction.atomic():
        peminjaman = get_object_or_404(
            PeminjamanAlat.objects.select_for_update(),
            pk=pk,
            status__in=['hilang', 'rusak'],
        )
        for item in _get_peminjaman_group_for_update(peminjaman).filter(status__in=['hilang', 'rusak']):
            item.status = 'digantikan'
            item.save(update_fields=['status', 'diperbarui_pada'])
            send_peminjaman_status_notification(item)
    return redirect('dashboard:home')


def _get_peminjaman_group_for_update(peminjaman):
    queryset = PeminjamanAlat.objects.select_for_update().select_related('barang')
    if peminjaman.transaksi_id:
        return queryset.filter(transaksi_id=peminjaman.transaksi_id)
    return queryset.filter(kode_pinjam=peminjaman.kode_pinjam)
