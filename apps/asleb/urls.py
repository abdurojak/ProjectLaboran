from django.urls import path

from .views import (
    AbsensiAslebCreateView,
    AbsensiAslebListView,
    AslebCreateView,
    AslebDeleteView,
    AslebDetailView,
    AslebListView,
    AslebUpdateView,
    HonorAslebCreateView,
    HonorAslebDeleteView,
    HonorAslebListView,
    HonorAslebUpdateView,
    SuratHonorAslebGenerateView,
    SuratHonorAslebListView,
    auto_assign_honor_transfers,
    confirm_honor_transfer,
    download_surat_honor,
    toggle_absensi_status,
)

app_name = 'asleb'

urlpatterns = [
    path('', AslebListView.as_view(), name='asleb_list'),
    path('tambah/', AslebCreateView.as_view(), name='asleb_create'),
    path('absensi/', AbsensiAslebListView.as_view(), name='absensi_list'),
    path('absensi/tambah/', AbsensiAslebCreateView.as_view(), name='absensi_create'),
    path('absensi/toggle/', toggle_absensi_status, name='absensi_toggle_status'),
    path('<int:pk>/', AslebDetailView.as_view(), name='asleb_detail'),
    path('<int:pk>/edit/', AslebUpdateView.as_view(), name='asleb_update'),
    path('<int:pk>/hapus/', AslebDeleteView.as_view(), name='asleb_delete'),
    path('honorarium/', HonorAslebListView.as_view(), name='honor_list'),
    path('honorarium/surat/', SuratHonorAslebListView.as_view(), name='surat_honor_list'),
    path('honorarium/surat/generate/', SuratHonorAslebGenerateView.as_view(), name='surat_honor_generate'),
    path('honorarium/surat/<int:pk>/download/', download_surat_honor, name='surat_honor_download'),
    path('honorarium/tambah/', HonorAslebCreateView.as_view(), name='honor_create'),
    path('honorarium/bagi-tugas-tf/', auto_assign_honor_transfers, name='honor_auto_assign_transfers'),
    path('honorarium/<int:pk>/konfirmasi-tf/', confirm_honor_transfer, name='honor_confirm_transfer'),
    path('honorarium/<int:pk>/edit/', HonorAslebUpdateView.as_view(), name='honor_update'),
    path('honorarium/<int:pk>/hapus/', HonorAslebDeleteView.as_view(), name='honor_delete'),
]
