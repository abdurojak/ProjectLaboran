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
    {'title': 'Jadwal Praktikum', 'icon': 'calendar-clock', 'url': 'jadwal:jadwal_list', 'namespace': 'jadwal'},
    {
        'title': 'Absensi Asleb',
        'icon': 'clipboard-check',
        'url': 'asleb:absensi_list',
        'namespace': 'asleb_absensi',
        'url_names': {'absensi_list', 'absensi_create'},
    },
    {
        'title': 'Data Asleb',
        'icon': 'users',
        'url': 'asleb:asleb_list',
        'namespace': 'asleb',
        'url_names': {'asleb_list', 'asleb_create', 'asleb_detail', 'asleb_update', 'asleb_delete'},
    },
    {'title': 'Pendaftaran Asleb', 'icon': 'user-round-plus', 'url': 'pendaftaran_asleb:pendaftaran_list', 'namespace': 'pendaftaran_asleb'},
    {
        'title': 'Rekap Honorarium Asleb',
        'icon': 'file-chart-column',
        'url': 'asleb:honor_list',
        'namespace': 'asleb',
        'url_names': {'honor_list', 'honor_create', 'honor_confirm_transfer', 'honor_update', 'honor_delete'},
    },
    {'title': 'Pengguna', 'icon': 'user-round', 'url': 'pengguna:list', 'namespace': 'pengguna'},
    {'title': 'Ruangan', 'icon': 'door-open', 'url': 'ruangan:ruangan_list', 'namespace': 'ruangan'},
    {'title': 'Pengaturan', 'icon': 'settings', 'url': '', 'namespace': ''},
]

MAHASISWA_VISIBLE_NAMESPACES = {'dashboard', 'kalender', 'peminjaman', 'jadwal', 'ruangan'}
ASISTEN_LAB_HIDDEN_TITLES = {'Rekap Honorarium Asleb', 'Pengaturan'}
ASISTEN_LAB_HIDDEN_NAMESPACES = {'inventaris', 'barang_tertinggal', 'asleb', 'pendaftaran_asleb', 'pengguna'}


def dashboard_sidebar(request):
    current_namespace = getattr(request.resolver_match, 'namespace', '')
    current_url_name = getattr(request.resolver_match, 'url_name', '')
    links = []

    for link in SIDEBAR_LINKS:
        current_pengguna = getattr(request, 'current_pengguna', None)
        if current_pengguna and current_pengguna.role == 'mahasiswa' and link['namespace'] not in MAHASISWA_VISIBLE_NAMESPACES:
            continue

        if current_pengguna and current_pengguna.role == 'asisten_lab':
            if link['namespace'] in ASISTEN_LAB_HIDDEN_NAMESPACES or link['title'] in ASISTEN_LAB_HIDDEN_TITLES:
                continue

        item = link.copy()
        url_names = item.get('url_names')
        if url_names:
            item['active'] = current_namespace == item['namespace'] and current_url_name in url_names
        else:
            item['active'] = bool(item['namespace'] and item['namespace'] == current_namespace)
        item.update(TONES['teal'] if item['active'] else TONES['gray'])
        links.append(item)

    return {
        'sidebar_links': links,
        'today': timezone.localdate(),
    }
