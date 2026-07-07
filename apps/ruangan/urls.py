from django.urls import path

from .views import FotoRuanganCreateView, FotoRuanganDeleteView, FotoRuanganUpdateView, RuanganListView

app_name = 'ruangan'

urlpatterns = [
    path('', RuanganListView.as_view(), name='ruangan_list'),
    path('<int:ruangan_pk>/foto/tambah/', FotoRuanganCreateView.as_view(), name='foto_create'),
    path('foto/<int:pk>/edit/', FotoRuanganUpdateView.as_view(), name='foto_update'),
    path('foto/<int:pk>/hapus/', FotoRuanganDeleteView.as_view(), name='foto_delete'),
]

