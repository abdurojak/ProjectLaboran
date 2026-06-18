from django.urls import path

from .views import (
    JadwalPraktikumCreateView,
    JadwalPraktikumDeleteView,
    JadwalPraktikumDetailView,
    JadwalPraktikumListView,
    JadwalPraktikumUpdateView,
)

app_name = 'jadwal'

urlpatterns = [
    path('', JadwalPraktikumListView.as_view(), name='jadwal_list'),
    path('tambah/', JadwalPraktikumCreateView.as_view(), name='jadwal_create'),
    path('<int:pk>/', JadwalPraktikumDetailView.as_view(), name='jadwal_detail'),
    path('<int:pk>/edit/', JadwalPraktikumUpdateView.as_view(), name='jadwal_update'),
    path('<int:pk>/hapus/', JadwalPraktikumDeleteView.as_view(), name='jadwal_delete'),
]

