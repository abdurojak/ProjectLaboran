from django.urls import path

from .views import (
    AslebCreateView,
    AslebDeleteView,
    AslebDetailView,
    AslebListView,
    AslebUpdateView,
)

app_name = 'asleb'

urlpatterns = [
    path('', AslebListView.as_view(), name='asleb_list'),
    path('tambah/', AslebCreateView.as_view(), name='asleb_create'),
    path('<int:pk>/', AslebDetailView.as_view(), name='asleb_detail'),
    path('<int:pk>/edit/', AslebUpdateView.as_view(), name='asleb_update'),
    path('<int:pk>/hapus/', AslebDeleteView.as_view(), name='asleb_delete'),
]
