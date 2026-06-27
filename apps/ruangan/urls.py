from django.urls import path

from .views import RuanganListView

app_name = 'ruangan'

urlpatterns = [
    path('', RuanganListView.as_view(), name='ruangan_list'),
]

