from django.urls import path

from .views import AdminBantuanView, BantuanView, EskalasiBantuanView, SettingsView


app_name = 'core'

urlpatterns = [
    path('', SettingsView.as_view(), name='settings'),
    path('bantuan/', BantuanView.as_view(), name='bantuan'),
    path('bantuan/hubungi-admin/', EskalasiBantuanView.as_view(), name='bantuan_escalate'),
    path('bantuan/admin/', AdminBantuanView.as_view(), name='bantuan_admin'),
]
