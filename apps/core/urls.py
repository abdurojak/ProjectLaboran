from django.urls import path

from .views import AdminBantuanSummaryView, AdminBantuanView, BantuanAsyncMessageView, BantuanView, BugErrorListView, EskalasiBantuanView, SettingsView


app_name = 'core'

urlpatterns = [
    path('', SettingsView.as_view(), name='settings'),
    path('bantuan/', BantuanView.as_view(), name='bantuan'),
    path('bantuan/kirim/', BantuanAsyncMessageView.as_view(), name='bantuan_async_message'),
    path('bantuan/hubungi-admin/', EskalasiBantuanView.as_view(), name='bantuan_escalate'),
    path('bantuan/admin/', AdminBantuanView.as_view(), name='bantuan_admin'),
    path('bantuan/admin/ringkasan/', AdminBantuanSummaryView.as_view(), name='bantuan_admin_summary'),
    path('bug-error/', BugErrorListView.as_view(), name='bug_error_list'),
]
