from django.urls import reverse

from apps.kalender.realtime import send_role_notification


def publish_barang_tertinggal_news(barang):
    location = barang.lokasi_ditemukan or 'area laboratorium'
    return send_role_notification('mahasiswa', {
        'event': 'lost_item.published',
        'source_key': f'barang-tertinggal:{barang.pk}:published',
        'title': f'Barang ditemukan: {barang.nama_barang}',
        'message': (
            f'{barang.jumlah_barang} {barang.jenis_barang.lower()} ditemukan di {location} '
            f'pada {barang.tanggal_ditemukan:%d-%m-%Y}. Periksa berita barang hilang jika ini milik Anda.'
        ),
        'notification_type': 'barang_tertinggal',
        'related_object_id': barang.pk,
        'related_url': reverse('barang_tertinggal:berita_detail', kwargs={'pk': barang.pk}),
        'refresh_paths': ['/', '/barang-tertinggal/berita/'],
        'auto_refresh': True,
        'icon': 'package-search',
        'icon_class': 'bg-amber-50 text-amber-700',
    })
