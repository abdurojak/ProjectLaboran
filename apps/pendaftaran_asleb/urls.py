from django.urls import path

from .views import (
    MataKuliahAslebCreateView,
    MataKuliahAslebDeleteView,
    MataKuliahAslebListView,
    MataKuliahAslebUpdateView,
    PendaftaranAslebCreateView,
    PendaftaranAslebDeleteView,
    PendaftaranAslebDetailView,
    PendaftaranAslebListView,
    PendaftaranAslebPublicCreateView,
    PendaftaranAslebSuccessView,
    PendaftaranAslebUpdateView,
    RekeningPendaftaranUpdateView,
    accept_pendaftaran,
    generate_all_accepted_asleb,
    generate_asleb,
    reject_pendaftaran,
    toggle_pendaftaran_status,
    update_periode_schedule,
    update_period_dates,
    end_period_manually,
)

app_name = 'pendaftaran_asleb'

urlpatterns = [
    path('', PendaftaranAslebListView.as_view(), name='pendaftaran_list'),
    path('daftar/', PendaftaranAslebPublicCreateView.as_view(), name='pendaftaran_public'),
    path('berhasil/', PendaftaranAslebSuccessView.as_view(), name='pendaftaran_success'),
    path('rekening/<int:pk>/edit/', RekeningPendaftaranUpdateView.as_view(), name='rekening_update'),
    path('matkul/', MataKuliahAslebListView.as_view(), name='matkul_list'),
    path('matkul/tambah/', MataKuliahAslebCreateView.as_view(), name='matkul_create'),
    path('matkul/<int:pk>/edit/', MataKuliahAslebUpdateView.as_view(), name='matkul_update'),
    path('matkul/<int:pk>/hapus/', MataKuliahAslebDeleteView.as_view(), name='matkul_delete'),
    path('tambah/', PendaftaranAslebCreateView.as_view(), name='pendaftaran_create'),
    path('<int:pk>/', PendaftaranAslebDetailView.as_view(), name='pendaftaran_detail'),
    path('<int:pk>/edit/', PendaftaranAslebUpdateView.as_view(), name='pendaftaran_update'),
    path('<int:pk>/hapus/', PendaftaranAslebDeleteView.as_view(), name='pendaftaran_delete'),
    path('<int:pk>/terima/', accept_pendaftaran, name='pendaftaran_accept'),
    path('<int:pk>/tolak/', reject_pendaftaran, name='pendaftaran_reject'),
    path('<int:pk>/generate-asleb/', generate_asleb, name='pendaftaran_generate_asleb'),
    path('generate-diterima/', generate_all_accepted_asleb, name='pendaftaran_generate_all_accepted'),
    path('toggle-status/', toggle_pendaftaran_status, name='pendaftaran_toggle_status'),
    path('periode/<int:pk>/jadwal/', update_periode_schedule, name='periode_schedule_update'),
    path('periode/<int:pk>/masa-tugas/', update_period_dates, name='periode_dates_update'),
    path('periode/<int:pk>/akhiri/', end_period_manually, name='periode_end'),
]
