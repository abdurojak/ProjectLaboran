from django.urls import path

from .views import SuratCreateView, SuratListView, SuratUpdateView, download_surat_pdf

app_name = 'surat'

urlpatterns = [
    path('', SuratListView.as_view(), name='list'),
    path('pengadaan/tambah/', SuratCreateView.as_view(), name='create'),
    path('pengadaan/<int:pk>/edit/', SuratUpdateView.as_view(), name='update'),
    path('pengadaan/<int:pk>/pdf/', download_surat_pdf, name='download_pdf'),
]
