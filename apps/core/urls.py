from django.urls import path

from .views import SettingsView


app_name = 'core'

urlpatterns = [
    path('', SettingsView.as_view(), name='settings'),
]
