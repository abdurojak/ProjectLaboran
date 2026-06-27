from django.urls import path

from .views import (
    FakultasCreateView,
    FakultasUpdateView,
    ForgotPasswordRequestView,
    MasterAkademikView,
    PenggunaChangePasswordView,
    PenggunaCreateView,
    PenggunaDeleteView,
    PenggunaDetailView,
    PenggunaListView,
    PenggunaLoginView,
    PenggunaLogoutView,
    PenggunaRegisterView,
    PenggunaVerifyProfilePhoneView,
    PenggunaUpdateProfileView,
    PenggunaUpdateView,
    PenggunaVerifyRegisterView,
    ProdiCreateView,
    ProdiUpdateView,
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
    path('master-akademik/', MasterAkademikView.as_view(), name='master_akademik'),
    path('master-akademik/fakultas/tambah/', FakultasCreateView.as_view(), name='fakultas_create'),
    path('master-akademik/fakultas/<int:pk>/edit/', FakultasUpdateView.as_view(), name='fakultas_update'),
    path('master-akademik/prodi/tambah/', ProdiCreateView.as_view(), name='prodi_create'),
    path('master-akademik/prodi/<int:pk>/edit/', ProdiUpdateView.as_view(), name='prodi_update'),
    path('tambah/', PenggunaCreateView.as_view(), name='create'),
    path('<int:pk>/', PenggunaDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', PenggunaUpdateView.as_view(), name='update'),
    path('<int:pk>/edit-profil/', PenggunaUpdateProfileView.as_view(), name='update_profile'),
    path('<int:pk>/verifikasi-no-hp/', PenggunaVerifyProfilePhoneView.as_view(), name='verify_profile_phone'),
    path('<int:pk>/ganti-password/', PenggunaChangePasswordView.as_view(), name='change_password'),
    path('<int:pk>/hapus/', PenggunaDeleteView.as_view(), name='delete'),
]
