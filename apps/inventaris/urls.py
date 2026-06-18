from django.urls import path

from .views import (
    BarangCreateView,
    BarangDeleteView,
    BarangDetailView,
    BarangListView,
    BarangUpdateView,
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
    path('barang/<int:pk>/', BarangDetailView.as_view(), name='barang_detail'),
    path('barang/<int:pk>/edit/', BarangUpdateView.as_view(), name='barang_update'),
    path('barang/<int:pk>/hapus/', BarangDeleteView.as_view(), name='barang_delete'),
    path('lokasi/', LokasiListView.as_view(), name='lokasi_list'),
    path('lokasi/tambah/', LokasiCreateView.as_view(), name='lokasi_create'),
    path('lokasi/<int:pk>/', LokasiDetailView.as_view(), name='lokasi_detail'),
    path('lokasi/<int:pk>/edit/', LokasiUpdateView.as_view(), name='lokasi_update'),
    path('lokasi/<int:pk>/hapus/', LokasiDeleteView.as_view(), name='lokasi_delete'),
]
