from django.urls import path

from .views import (
    DashboardView,
    accept_jadwal,
    accept_peminjaman,
    reject_jadwal,
    mark_peminjaman_broken,
    mark_peminjaman_lost,
    mark_peminjaman_replaced,
    mark_peminjaman_returned,
    reject_peminjaman,
)

app_name = 'dashboard'

urlpatterns = [
    path('', DashboardView.as_view(), name='home'),
    path('jadwal/<int:pk>/terima/', accept_jadwal, name='jadwal_accept'),
    path('jadwal/<int:pk>/tolak/', reject_jadwal, name='jadwal_reject'),
    path('peminjaman/<int:pk>/terima/', accept_peminjaman, name='peminjaman_accept'),
    path('peminjaman/<int:pk>/tolak/', reject_peminjaman, name='peminjaman_reject'),
    path('peminjaman/<int:pk>/dikembalikan/', mark_peminjaman_returned, name='peminjaman_returned'),
    path('peminjaman/<int:pk>/hilang/', mark_peminjaman_lost, name='peminjaman_lost'),
    path('peminjaman/<int:pk>/rusak/', mark_peminjaman_broken, name='peminjaman_broken'),
    path('peminjaman/<int:pk>/digantikan/', mark_peminjaman_replaced, name='peminjaman_replaced'),
]

