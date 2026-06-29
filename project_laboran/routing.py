from django.urls import path

from apps.core.consumers import BantuanChatConsumer


websocket_urlpatterns = [
    path('ws/bantuan/<int:percakapan_id>/', BantuanChatConsumer.as_asgi()),
]
