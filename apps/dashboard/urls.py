from django.urls import path

from .views import DashboardView, accept_peminjaman, mark_peminjaman_replaced, reject_peminjaman

app_name = 'dashboard'

urlpatterns = [
    path('', DashboardView.as_view(), name='home'),
    path('peminjaman/<int:pk>/terima/', accept_peminjaman, name='peminjaman_accept'),
    path('peminjaman/<int:pk>/tolak/', reject_peminjaman, name='peminjaman_reject'),
    path('peminjaman/<int:pk>/digantikan/', mark_peminjaman_replaced, name='peminjaman_replaced'),
]

