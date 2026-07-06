from django.urls import path

from apps.core.consumers import BantuanChatConsumer
from apps.kalender.routing import websocket_urlpatterns as notification_websocket_urlpatterns


websocket_urlpatterns = [
    path('ws/bantuan/<int:percakapan_id>/', BantuanChatConsumer.as_asgi()),
] + notification_websocket_urlpatterns
