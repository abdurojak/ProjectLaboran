from django.urls import path

from .views import (
    PeminjamanAlatCreateView,
    PeminjamanAlatDeleteView,
    PeminjamanAlatDetailView,
    PeminjamanAlatListView,
    PeminjamanAlatUpdateView,
)

app_name = 'peminjaman'

urlpatterns = [
    path('', PeminjamanAlatListView.as_view(), name='peminjaman_list'),
    path('tambah/', PeminjamanAlatCreateView.as_view(), name='peminjaman_create'),
    path('<int:pk>/', PeminjamanAlatDetailView.as_view(), name='peminjaman_detail'),
    path('<int:pk>/edit/', PeminjamanAlatUpdateView.as_view(), name='peminjaman_update'),
    path('<int:pk>/hapus/', PeminjamanAlatDeleteView.as_view(), name='peminjaman_delete'),
]

