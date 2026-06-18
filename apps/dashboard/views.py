from django.utils import timezone
from django.db.models import Sum
from django.views.generic import TemplateView

from apps.inventaris.models import Barang


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

        context['total_barang'] = barang_qs.count()
        context['total_unit'] = barang_qs.aggregate(total=Sum('jumlah'))['total'] or 0
        context['kondisi_baik'] = barang_qs.filter(kondisi='baik').count()
        context['butuh_perhatian'] = barang_qs.exclude(kondisi='baik').count()
        context['barang_terbaru'] = barang_qs.order_by('-dibuat_pada')[:5]
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
                'value': 0,
                'note': 'Disiapkan untuk modul berikutnya',
                'icon': 'arrow-left-right',
                'tone': 'orange',
            },
            {
                'label': 'Jadwal Hari Ini',
                'value': 0,
                'note': 'Belum ada jadwal aktif',
                'icon': 'calendar-days',
                'tone': 'blue',
            },
            {
                'label': 'Laporan Bulan Ini',
                'value': 0,
                'note': 'Menunggu modul laporan',
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
                'description': 'Pencatatan peminjaman dan pengembalian alat akan ditambahkan berikutnya.',
                'url': '',
                'status': 'Segera Hadir',
                'icon': 'arrow-left-right',
                'tone': 'orange',
            },
            {
                'title': 'Jadwal Praktikum',
                'description': 'Penjadwalan sesi praktikum dan pemakaian ruang akan menyusul.',
                'url': '',
                'status': 'Segera Hadir',
                'icon': 'calendar-days',
                'tone': 'blue',
            },
            {
                'title': 'Data Siswa',
                'description': 'Kelola data siswa, kelas, dan program praktikum pada tahap berikutnya.',
                'url': '',
                'status': 'Segera Hadir',
                'icon': 'users',
                'tone': 'green',
            },
            {
                'title': 'Laporan',
                'description': 'Ringkasan aktivitas dan rekap inventaris akan tersedia di modul ini.',
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
                'description': 'Pengaturan ruangan laboratorium dan ketersediaannya akan ditambahkan.',
                'url': '',
                'status': 'Segera Hadir',
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
        context['sidebar_links'] = self._decorate_items([
            {'title': 'Dashboard', 'icon': 'layout-grid', 'url': 'dashboard:home', 'active': True, 'tone': 'teal'},
            {'title': 'Inventaris', 'icon': 'package', 'url': 'inventaris:barang_list', 'active': False, 'tone': 'gray'},
            {'title': 'Peminjaman Alat', 'icon': 'arrow-left-right', 'url': '', 'active': False, 'tone': 'gray'},
            {'title': 'Jadwal Praktikum', 'icon': 'calendar-days', 'url': '', 'active': False, 'tone': 'gray'},
            {'title': 'Data Siswa', 'icon': 'users', 'url': '', 'active': False, 'tone': 'gray'},
            {'title': 'Laporan', 'icon': 'file-chart-column', 'url': '', 'active': False, 'tone': 'gray'},
            {'title': 'Pengguna', 'icon': 'user-round', 'url': '', 'active': False, 'tone': 'gray'},
            {'title': 'Ruangan', 'icon': 'door-open', 'url': '', 'active': False, 'tone': 'gray'},
            {'title': 'Pengaturan', 'icon': 'settings', 'url': '', 'active': False, 'tone': 'gray'},
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
                'detail': 'Aktivitas peminjaman akan aktif saat modul peminjaman selesai dibangun.',
                'tone': 'orange',
            },
            {
                'time': '09:30',
                'title': 'Jadwal praktikum dibuat',
                'detail': 'Jadwal harian laboratorium nantinya ditampilkan otomatis pada bagian ini.',
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
                'title': 'Buat Jadwal Praktikum',
                'description': 'Segera aktif setelah modul jadwal ditambahkan.',
                'url': '',
                'icon': 'calendar-plus-2',
                'tone': 'blue',
            },
            {
                'title': 'Cetak Laporan Inventaris',
                'description': 'Akan tersedia setelah modul laporan disiapkan.',
                'url': '',
                'icon': 'printer',
                'tone': 'purple',
            },
        ])
        return context
