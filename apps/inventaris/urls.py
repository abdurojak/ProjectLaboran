from django.urls import path

from .views import (
    BarangCreateView,
    BarangDeleteView,
    BarangDetailView,
    BarangListView,
    BarangUpdateView,
)

app_name = 'inventaris'

urlpatterns = [
    path('', BarangListView.as_view(), name='barang_list'),
    path('barang/tambah/', BarangCreateView.as_view(), name='barang_create'),
    path('barang/<int:pk>/', BarangDetailView.as_view(), name='barang_detail'),
    path('barang/<int:pk>/edit/', BarangUpdateView.as_view(), name='barang_update'),
    path('barang/<int:pk>/hapus/', BarangDeleteView.as_view(), name='barang_delete'),
]
