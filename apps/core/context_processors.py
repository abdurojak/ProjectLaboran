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
    {'title': 'Dashboard', 'icon': 'layout-grid', 'url': 'dashboard:home', 'namespace': 'dashboard', 'tone': 'teal'},
    {'title': 'Inventaris', 'icon': 'package', 'url': 'inventaris:barang_list', 'namespace': 'inventaris', 'tone': 'gray'},
    {'title': 'Barang Tertinggal', 'icon': 'briefcase', 'url': 'barang_tertinggal:list', 'namespace': 'barang_tertinggal', 'tone': 'gray'},
    {'title': 'Peminjaman Alat', 'icon': 'arrow-left-right', 'url': 'peminjaman:peminjaman_list', 'namespace': 'peminjaman', 'tone': 'gray'},
    {'title': 'Jadwal Praktikum', 'icon': 'calendar-days', 'url': 'jadwal:jadwal_list', 'namespace': 'jadwal', 'tone': 'gray'},
    {'title': 'Data Asleb', 'icon': 'users', 'url': '', 'namespace': '', 'tone': 'gray'},
    {'title': 'Rekap Honorarium Asleb', 'icon': 'file-chart-column', 'url': '', 'namespace': '', 'tone': 'gray'},
    {'title': 'Pengguna', 'icon': 'user-round', 'url': '', 'namespace': '', 'tone': 'gray'},
    {'title': 'Ruangan', 'icon': 'door-open', 'url': 'ruangan:ruangan_list', 'namespace': 'ruangan', 'tone': 'gray'},
    {'title': 'Pengaturan', 'icon': 'settings', 'url': '', 'namespace': '', 'tone': 'gray'},
]


def dashboard_sidebar(request):
    current_namespace = getattr(request.resolver_match, 'namespace', '')
    links = []

    for link in SIDEBAR_LINKS:
        item = link.copy()
        item.update(TONES.get(item['tone'], TONES['gray']))
        item['active'] = bool(item['namespace'] and item['namespace'] == current_namespace)
        links.append(item)

    return {
        'sidebar_links': links,
        'today': timezone.localdate(),
    }
