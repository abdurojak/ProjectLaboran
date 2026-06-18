from django.urls import path

from .views import (
    KegiatanKalenderCreateView,
    KegiatanKalenderDeleteView,
    KegiatanKalenderDetailView,
    KegiatanKalenderListView,
    KegiatanKalenderUpdateView,
    NotifikasiListView,
)

app_name = 'kalender'

urlpatterns = [
    path('', KegiatanKalenderListView.as_view(), name='kegiatan_list'),
    path('tambah/', KegiatanKalenderCreateView.as_view(), name='kegiatan_create'),
    path('notifikasi/', NotifikasiListView.as_view(), name='notifikasi_list'),
    path('<int:pk>/', KegiatanKalenderDetailView.as_view(), name='kegiatan_detail'),
    path('<int:pk>/edit/', KegiatanKalenderUpdateView.as_view(), name='kegiatan_update'),
    path('<int:pk>/hapus/', KegiatanKalenderDeleteView.as_view(), name='kegiatan_delete'),
]

