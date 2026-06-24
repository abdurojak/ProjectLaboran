from django.utils import timezone


TONES = {
    'teal': {
        'icon_bg': 'bg-cyan-50',
        'icon_text': 'text-cyan-700',
    },
    'orange': {
        'icon_bg': 'bg-amber-50',
        'icon_text': 'text-amber-600',
    },
    'blue': {
        'icon_bg': 'bg-blue-50',
        'icon_text': 'text-blue-700',
    },
    'purple': {
        'icon_bg': 'bg-violet-50',
        'icon_text': 'text-violet-700',
    },
    'green': {
        'icon_bg': 'bg-emerald-50',
        'icon_text': 'text-emerald-700',
    },
    'gray': {
        'icon_bg': 'bg-slate-100',
        'icon_text': 'text-slate-500',
    },
}


SIDEBAR_LINKS = [
    {'title': 'Dashboard', 'icon': 'layout-grid', 'url': 'dashboard:home', 'namespace': 'dashboard'},
    {'title': 'Kalender', 'icon': 'calendar-days', 'url': 'kalender:kegiatan_list', 'namespace': 'kalender'},
    {'title': 'Inventaris', 'icon': 'package', 'url': 'inventaris:barang_list', 'namespace': 'inventaris'},
    {'title': 'Barang Tertinggal', 'icon': 'briefcase', 'url': 'barang_tertinggal:list', 'namespace': 'barang_tertinggal'},
    {'title': 'Peminjaman Alat', 'icon': 'arrow-left-right', 'url': 'peminjaman:peminjaman_list', 'namespace': 'peminjaman'},
    {'title': 'Jadwal Praktikum', 'icon': 'calendar-days', 'url': 'jadwal:jadwal_list', 'namespace': 'jadwal'},
    {'title': 'Data Asleb', 'icon': 'users', 'url': 'asleb:asleb_list', 'namespace': 'asleb'},
    {'title': 'Pendaftaran Asleb', 'icon': 'user-round-plus', 'url': 'pendaftaran_asleb:pendaftaran_list', 'namespace': 'pendaftaran_asleb'},
    {'title': 'Rekap Honorarium Asleb', 'icon': 'file-chart-column', 'url': '', 'namespace': ''},
    {'title': 'Pengguna', 'icon': 'user-round', 'url': 'pengguna:list', 'namespace': 'pengguna'},
    {'title': 'Ruangan', 'icon': 'door-open', 'url': 'ruangan:ruangan_list', 'namespace': 'ruangan'},
    {'title': 'Pengaturan', 'icon': 'settings', 'url': '', 'namespace': ''},
]

MAHASISWA_VISIBLE_NAMESPACES = {'dashboard', 'peminjaman', 'jadwal'}


def dashboard_sidebar(request):
    current_namespace = getattr(request.resolver_match, 'namespace', '')
    links = []

    for link in SIDEBAR_LINKS:
        current_pengguna = getattr(request, 'current_pengguna', None)
        if current_pengguna and current_pengguna.role == 'mahasiswa' and link['namespace'] not in MAHASISWA_VISIBLE_NAMESPACES:
            continue

        item = link.copy()
        item['active'] = bool(item['namespace'] and item['namespace'] == current_namespace)
        item.update(TONES['teal'] if item['active'] else TONES['gray'])
        links.append(item)

    return {
        'sidebar_links': links,
        'today': timezone.localdate(),
    }
