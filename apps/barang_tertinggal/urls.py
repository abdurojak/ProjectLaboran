from django.urls import path

from .views import (
    BarangTertinggalCreateView,
    BarangTertinggalDeleteView,
    BarangTertinggalDetailView,
    BarangTertinggalListView,
    BarangTertinggalUpdateView,
)

app_name = 'barang_tertinggal'

urlpatterns = [
    path('', BarangTertinggalListView.as_view(), name='list'),
    path('tambah/', BarangTertinggalCreateView.as_view(), name='create'),
    path('<int:pk>/', BarangTertinggalDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', BarangTertinggalUpdateView.as_view(), name='update'),
    path('<int:pk>/hapus/', BarangTertinggalDeleteView.as_view(), name='delete'),
]

