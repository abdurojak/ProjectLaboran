from datetime import date, datetime, timedelta


PERAYAAN_TETAP_INDONESIA = [
    (1, 1, 'Tahun Baru Masehi', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (2, 17, 'Tahun Baru Imlek', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (4, 21, 'Hari Kartini', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (5, 1, 'Hari Buruh', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (5, 2, 'Hari Pendidikan Nasional', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (5, 20, 'Hari Kebangkitan Nasional', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (6, 1, 'Hari Lahir Pancasila', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (8, 17, 'Hari Kemerdekaan Republik Indonesia', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (10, 1, 'Hari Kesaktian Pancasila', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (10, 28, 'Hari Sumpah Pemuda', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (11, 10, 'Hari Pahlawan', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (12, 22, 'Hari Ibu', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
    (12, 25, 'Hari Natal', 'Hari perayaan nasional otomatis', '#f97316', 'perayaan'),
]


PERAYAAN_TRISAKTI = [
    (5, 12, 'Peringatan Tragedi Trisakti', 'Universitas Trisakti', '#0f766e', 'trisakti'),
    (11, 29, 'Dies Natalis Universitas Trisakti', 'Universitas Trisakti', '#0f766e', 'trisakti'),
]


def get_perayaan_items(base_year):
    items = []

    for year in range(base_year - 1, base_year + 2):
        for month, day, title, location, color, category in PERAYAAN_TETAP_INDONESIA + PERAYAAN_TRISAKTI:
            items.append(
                {
                    'judul': title,
                    'tanggal': date(year, month, day),
                    'lokasi': location,
                    'color': color,
                    'kategori': category,
                }
            )

    return items


def get_perayaan_calendar_events(base_year):
    events = []

    for item in get_perayaan_items(base_year):
        events.append(
            {
                'title': item['judul'],
                'start': item['tanggal'].isoformat(),
                'allDay': True,
                'backgroundColor': item['color'],
                'borderColor': item['color'],
                'textColor': '#ffffff',
                'extendedProps': {
                    'lokasi': item['lokasi'],
                    'notifikasi': 'Otomatis',
                    'kategori': item['kategori'],
                },
            }
        )

    return events


def get_perayaan_notifications(today, days=7):
    limit_date = today + timedelta(days=days)
    notifications = []

    for item in get_perayaan_items(today.year):
        if today <= item['tanggal'] <= limit_date:
            notifications.append(
                {
                    'judul': item['judul'],
                    'tanggal': item['tanggal'],
                    'waktu_label': 'Sehari penuh',
                    'lokasi': item['lokasi'],
                    'deskripsi': 'Hari perayaan otomatis dari kalender.',
                    'url': '',
                    'icon': 'calendar-heart' if item['kategori'] == 'perayaan' else 'school',
                    'icon_class': 'bg-orange-50 text-orange-600' if item['kategori'] == 'perayaan' else 'bg-teal-50 text-teal-700',
                    'badge': 'Perayaan',
                }
            )

    return sorted(notifications, key=lambda item: item['tanggal'])


def build_manual_notification(kegiatan, detail_url):
    waktu_label = kegiatan.waktu_mulai.strftime('%H:%M')
    if kegiatan.waktu_selesai:
        waktu_label = f'{waktu_label} - {kegiatan.waktu_selesai.strftime("%H:%M")}'

    return {
        'judul': kegiatan.judul,
        'tanggal': kegiatan.tanggal,
        'waktu_label': waktu_label,
        'lokasi': kegiatan.lokasi or '-',
        'deskripsi': kegiatan.deskripsi or 'Tidak ada deskripsi tambahan.',
        'url': detail_url,
        'icon': 'bell-ring',
        'icon_class': 'bg-blue-50 text-blue-700',
        'badge': 'Kegiatan',
    }
