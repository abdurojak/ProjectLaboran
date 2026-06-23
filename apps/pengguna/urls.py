from django.urls import path

from .views import (
    ForgotPasswordRequestView,
    PenggunaCreateView,
    PenggunaDeleteView,
    PenggunaDetailView,
    PenggunaListView,
    PenggunaLoginView,
    PenggunaLogoutView,
    PenggunaRegisterView,
    PenggunaUpdateView,
    PenggunaVerifyRegisterView,
    ResetPasswordView,
)

app_name = 'pengguna'

urlpatterns = [
    path('login/', PenggunaLoginView.as_view(), name='login'),
    path('register/', PenggunaRegisterView.as_view(), name='register'),
    path('register/verifikasi/', PenggunaVerifyRegisterView.as_view(), name='verify_register'),
    path('forgot-password/', ForgotPasswordRequestView.as_view(), name='forgot_password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('logout/', PenggunaLogoutView.as_view(), name='logout'),
    path('', PenggunaListView.as_view(), name='list'),
    path('tambah/', PenggunaCreateView.as_view(), name='create'),
    path('<int:pk>/', PenggunaDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', PenggunaUpdateView.as_view(), name='update'),
    path('<int:pk>/hapus/', PenggunaDeleteView.as_view(), name='delete'),
]
