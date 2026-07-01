from django.urls import path

from .views import (
    PeminjamanAlatCreateView,
    PeminjamanAlatDeleteView,
    PeminjamanAlatDetailView,
    PeminjamanAlatListView,
    PeminjamanAlatUpdateView,
    barang_options,
    bulk_update_status,
    update_detail_status,
)

app_name = 'peminjaman'

urlpatterns = [
    path('', PeminjamanAlatListView.as_view(), name='peminjaman_list'),
    path('tambah/', PeminjamanAlatCreateView.as_view(), name='peminjaman_create'),
    path('bulk-update-status/', bulk_update_status, name='peminjaman_bulk_update'),
    path('barang-options/', barang_options, name='barang_options'),
    path('<int:pk>/', PeminjamanAlatDetailView.as_view(), name='peminjaman_detail'),
    path('<int:pk>/status/', update_detail_status, name='peminjaman_detail_status_update'),
    path('<int:pk>/edit/', PeminjamanAlatUpdateView.as_view(), name='peminjaman_update'),
    path('<int:pk>/hapus/', PeminjamanAlatDeleteView.as_view(), name='peminjaman_delete'),
]
