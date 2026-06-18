from django.urls import path

from .views import BarangTertinggalListView

app_name = 'barang_tertinggal'

urlpatterns = [
    path('', BarangTertinggalListView.as_view(), name='list'),
]

