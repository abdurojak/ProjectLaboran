from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Sum
from django.views.generic import TemplateView

from apps.inventaris.models import Barang
from apps.jadwal.models import JadwalPraktikum
from apps.kalender.models import KegiatanKalender
from apps.peminjaman.models import PeminjamanAlat


class DashboardView(TemplateView):
    template_name = 'dashboard/home.html'

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        barang_qs = Barang.objects.all()
        jadwal_qs = JadwalPraktikum.objects.all()
        kegiatan_qs = KegiatanKalender.objects.all()
        peminjaman_qs = PeminjamanAlat.objects.select_related('barang')
        peminjaman_aktif = peminjaman_qs.exclude(status='dikembalikan')

        context['total_barang'] = barang_qs.count()
        context['total_unit'] = barang_qs.aggregate(total=Sum('jumlah'))['total'] or 0
        context['kondisi_baik'] = barang_qs.filter(kondisi='baik').count()
        context['butuh_perhatian'] = barang_qs.exclude(kondisi='baik').count()
        context['barang_terbaru'] = barang_qs.order_by('-dibuat_pada')[:5]
        context['peminjaman_terbaru'] = peminjaman_qs[:5]
        context['peminjaman_diajukan'] = peminjaman_qs.filter(status='diajukan')[:6]
        context['peminjaman_perlu_diganti'] = peminjaman_qs.filter(status__in=['hilang', 'rusak'])[:6]
        context['today'] = timezone.localdate()
        context['stats_cards'] = self._decorate_items([
            {
                'label': 'Total Barang',
                'value': context['total_barang'],
                'note': 'Semua barang terdaftar',
                'icon': 'package',
                'tone': 'teal',
            },
            {
                'label': 'Peminjaman Aktif',
                'value': peminjaman_aktif.count(),
                'note': 'Transaksi yang belum ditandai selesai',
                'icon': 'arrow-left-right',
                'tone': 'orange',
            },
            {
                'label': 'Jadwal Hari Ini',
                'value': jadwal_qs.filter(tanggal=context['today']).count(),
                'note': 'Jadwal praktikum yang terdaftar hari ini',
                'icon': 'calendar-days',
                'tone': 'blue',
            },
            {
                'label': 'Honorarium Bulan Ini',
                'value': 0,
                'note': 'Menunggu modul rekap honorarium asleb',
                'icon': 'file-chart-column',
                'tone': 'purple',
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
                'title': 'Data Asleb',
                'description': 'Kelola data asisten laboratorium untuk membantu operasional praktikum.',
                'url': '',
                'status': 'Segera Hadir',
                'icon': 'users',
                'tone': 'green',
            },
            {
                'title': 'Rekap Honorarium Asleb',
                'description': 'Rekap honor, pembayaran, dan ringkasan penggajian asleb akan tersedia di modul ini.',
                'url': '',
                'status': 'Segera Hadir',
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
                'title': 'Pengguna baru ditambahkan',
                'detail': 'Manajemen pengguna akan dihubungkan setelah modul berikutnya disiapkan.',
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
    peminjaman = get_object_or_404(PeminjamanAlat, pk=pk, status='diajukan')
    peminjaman.status = 'dipinjam'
    peminjaman.save(update_fields=['status', 'diperbarui_pada'])
    return redirect('dashboard:home')


@require_POST
def reject_peminjaman(request, pk):
    peminjaman = get_object_or_404(PeminjamanAlat, pk=pk, status='diajukan')
    peminjaman.delete()
    return redirect('dashboard:home')


@require_POST
def mark_peminjaman_replaced(request, pk):
    peminjaman = get_object_or_404(PeminjamanAlat, pk=pk, status__in=['hilang', 'rusak'])
    peminjaman.status = 'digantikan'
    peminjaman.save(update_fields=['status', 'diperbarui_pada'])
    return redirect('dashboard:home')
