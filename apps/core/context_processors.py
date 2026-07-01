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
    {
        'title': 'Inventaris',
        'icon': 'package',
        'url': 'inventaris:barang_list',
        'namespace': 'inventaris',
        'url_names': {
            'barang_list',
            'barang_create',
            'inventaris_detail',
            'detail_barang_create',
            'detail_barang_update',
            'detail_barang_delete',
            'barang_detail',
            'barang_update',
            'barang_delete',
            'lokasi_list',
            'lokasi_create',
            'lokasi_detail',
            'lokasi_update',
            'lokasi_delete',
        },
    },
    {'title': 'Barang Tertinggal', 'icon': 'briefcase', 'url': 'barang_tertinggal:list', 'namespace': 'barang_tertinggal'},
    {'title': 'Peminjaman Alat', 'icon': 'arrow-left-right', 'url': 'peminjaman:peminjaman_list', 'namespace': 'peminjaman'},
    {'title': 'Jadwal Praktikum', 'icon': 'calendar-clock', 'url': 'jadwal:jadwal_list', 'namespace': 'jadwal'},
    {
        'title': 'Asisten Laboratorium',
        'icon': 'users-round',
        'namespace': 'asisten_laboratorium',
        'children': [
            {
                'title': 'Absensi Aslab',
                'icon': 'clipboard-check',
                'url': 'asleb:absensi_list',
                'namespace': 'asleb',
                'url_names': {'absensi_list', 'absensi_create', 'absensi_toggle_status', 'modul_create', 'modul_update', 'modul_delete', 'modul_download'},
                'roles': {'admin', 'laboran', 'asisten_lab'},
            },
            {
                'title': 'Nilai & Absensi Mahasiswa',
                'icon': 'clipboard-pen-line',
                'url': 'asleb:praktikum_mahasiswa_list',
                'namespace': 'asleb',
                'url_names': {'praktikum_mahasiswa_list', 'praktikum_peserta_create', 'praktikum_peserta_delete', 'praktikum_nilai'},
                'roles': {'admin', 'laboran', 'asisten_lab'},
            },
            {
                'title': 'Data Aslab',
                'icon': 'contact-round',
                'url': 'asleb:asleb_list',
                'namespace': 'asleb',
                'url_names': {'asleb_list', 'asleb_create', 'asleb_detail', 'asleb_update', 'asleb_delete'},
                'roles': {'admin', 'laboran'},
            },
            {
                'title': 'Pendaftaran Aslab',
                'icon': 'user-round-plus',
                'url': 'pendaftaran_asleb:pendaftaran_list',
                'namespace': 'pendaftaran_asleb',
                'url_names': {
                    'pendaftaran_list', 'pendaftaran_create', 'pendaftaran_detail', 'pendaftaran_update',
                    'pendaftaran_delete', 'pendaftaran_accept', 'pendaftaran_reject',
                    'pendaftaran_generate_asleb', 'pendaftaran_generate_all_accepted',
                    'pendaftaran_toggle_status', 'periode_schedule_update', 'matkul_list',
                    'matkul_create', 'matkul_update', 'matkul_delete',
                },
                'roles': {'admin', 'laboran'},
            },
            {
                'title': 'Daftar Aslab',
                'icon': 'send',
                'url': 'pendaftaran_asleb:pendaftaran_public',
                'namespace': 'pendaftaran_asleb',
                'url_names': {'pendaftaran_public', 'pendaftaran_success'},
                'roles': {'mahasiswa', 'asisten_lab'},
            },
            {
                'title': 'Rekap Honorarium',
                'icon': 'file-chart-column',
                'url': 'asleb:honor_list',
                'namespace': 'asleb',
                'url_names': {
                    'honor_list', 'honor_create', 'honor_auto_assign_transfers',
                    'honor_confirm_transfer', 'honor_update', 'honor_delete',
                    'surat_honor_list', 'surat_honor_generate', 'surat_honor_download',
                },
                'roles': {'admin', 'laboran'},
            },
        ],
    },
    {
        'title': 'Pengguna',
        'icon': 'user-round',
        'url': 'pengguna:list',
        'namespace': 'pengguna',
        'url_names': {'list', 'create', 'detail', 'update', 'update_profile', 'verify_profile_phone', 'change_password', 'delete'},
    },
    {
        'title': 'Master Akademik',
        'icon': 'graduation-cap',
        'url': 'pengguna:master_akademik',
        'namespace': 'pengguna',
        'url_names': {'master_akademik', 'fakultas_create', 'fakultas_update', 'prodi_create', 'prodi_update'},
    },
    {'title': 'Ruangan', 'icon': 'door-open', 'url': 'ruangan:ruangan_list', 'namespace': 'ruangan'},
    {'title': 'Pengaturan', 'icon': 'settings', 'url': 'core:settings', 'namespace': 'core'},
]

MAHASISWA_VISIBLE_NAMESPACES = {'core', 'dashboard', 'kalender', 'peminjaman', 'jadwal', 'ruangan'}
ASISTEN_LAB_HIDDEN_NAMESPACES = {'inventaris', 'barang_tertinggal', 'asleb', 'pendaftaran_asleb', 'pengguna'}


def _set_active(item, current_namespace, current_url_name):
    url_names = item.get('url_names')
    if url_names:
        active_namespace = item.get('active_namespace', item['namespace'])
        return current_namespace == active_namespace and current_url_name in url_names
    return bool(item.get('namespace') and item['namespace'] == current_namespace)


def dashboard_sidebar(request):
    current_namespace = getattr(request.resolver_match, 'namespace', '')
    current_url_name = getattr(request.resolver_match, 'url_name', '')
    links = []

    for link in SIDEBAR_LINKS:
        current_pengguna = getattr(request, 'current_pengguna', None)
        role = getattr(current_pengguna, 'role', None)

        if link.get('children'):
            children = []
            for child_link in link['children']:
                if role and role not in child_link.get('roles', set()):
                    continue
                child = child_link.copy()
                child['active'] = _set_active(child, current_namespace, current_url_name)
                child.update(TONES['teal'] if child['active'] else TONES['gray'])
                children.append(child)
            if not children:
                continue
            item = link.copy()
            item['children'] = children
            item['active'] = any(child['active'] for child in children)
            item['expanded'] = item['active']
            item.update(TONES['teal'] if item['active'] else TONES['gray'])
            links.append(item)
            continue

        if current_pengguna and current_pengguna.role == 'mahasiswa' and link['namespace'] not in MAHASISWA_VISIBLE_NAMESPACES:
            continue

        if current_pengguna and current_pengguna.role == 'asisten_lab':
            if link['namespace'] in ASISTEN_LAB_HIDDEN_NAMESPACES:
                continue

        item = link.copy()
        item['active'] = _set_active(item, current_namespace, current_url_name)
        item.update(TONES['teal'] if item['active'] else TONES['gray'])
        links.append(item)

    return {
        'sidebar_links': links,
        'today': timezone.localdate(),
    }
