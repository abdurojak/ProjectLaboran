from django.urls import path

from .views import (
    BarangCreateView,
    BarangDeleteView,
    BarangDetailView,
    BarangListView,
    BarangUpdateView,
    DetailBarangCreateView,
    DetailBarangDeleteView,
    DetailBarangUpdateView,
    InventarisBarangDetailView,
    LokasiCreateView,
    LokasiDeleteView,
    LokasiDetailView,
    LokasiListView,
    LokasiUpdateView,
)

app_name = 'inventaris'

urlpatterns = [
    path('', BarangListView.as_view(), name='barang_list'),
    path('barang/tambah/', BarangCreateView.as_view(), name='barang_create'),
    path('inventaris/<int:pk>/', InventarisBarangDetailView.as_view(), name='inventaris_detail'),
    path('inventaris/<int:inventaris_pk>/detail/tambah/', DetailBarangCreateView.as_view(), name='detail_barang_create'),
    path('detail-barang/<int:pk>/edit/', DetailBarangUpdateView.as_view(), name='detail_barang_update'),
    path('detail-barang/<int:pk>/hapus/', DetailBarangDeleteView.as_view(), name='detail_barang_delete'),
    path('barang/<int:pk>/', BarangDetailView.as_view(), name='barang_detail'),
    path('barang/<int:pk>/edit/', BarangUpdateView.as_view(), name='barang_update'),
    path('barang/<int:pk>/hapus/', BarangDeleteView.as_view(), name='barang_delete'),
    path('lokasi/', LokasiListView.as_view(), name='lokasi_list'),
    path('lokasi/tambah/', LokasiCreateView.as_view(), name='lokasi_create'),
    path('lokasi/<int:pk>/', LokasiDetailView.as_view(), name='lokasi_detail'),
    path('lokasi/<int:pk>/edit/', LokasiUpdateView.as_view(), name='lokasi_update'),
    path('lokasi/<int:pk>/hapus/', LokasiDeleteView.as_view(), name='lokasi_delete'),
]
