from django.urls import path

from .views import (
    PenggunaCreateView,
    PenggunaDeleteView,
    PenggunaDetailView,
    PenggunaListView,
    PenggunaLoginView,
    PenggunaLogoutView,
    PenggunaRegisterView,
    PenggunaUpdateView,
)

app_name = 'pengguna'

urlpatterns = [
    path('login/', PenggunaLoginView.as_view(), name='login'),
    path('register/', PenggunaRegisterView.as_view(), name='register'),
    path('logout/', PenggunaLogoutView.as_view(), name='logout'),
    path('', PenggunaListView.as_view(), name='list'),
    path('tambah/', PenggunaCreateView.as_view(), name='create'),
    path('<int:pk>/', PenggunaDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', PenggunaUpdateView.as_view(), name='update'),
    path('<int:pk>/hapus/', PenggunaDeleteView.as_view(), name='delete'),
]
