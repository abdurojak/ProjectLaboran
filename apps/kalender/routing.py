from django.urls import path

from .consumers import NotificationConsumer


websocket_urlpatterns = [
    path('ws/notifikasi/', NotificationConsumer.as_asgi()),
]
