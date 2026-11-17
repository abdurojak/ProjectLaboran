import json
from django.utils import timezone

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.pengguna.models import Pengguna

from .models import Notifikasi
from .realtime import role_group_name, user_group_name


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.pengguna = await self.get_pengguna()
        if not self.pengguna:
            await self.close(code=4401)
            return

        self.groups = [
            user_group_name(self.pengguna.pk),
            role_group_name(self.pengguna.role),
            'labhub_presence',
        ]
        for group_name in self.groups:
            await self.channel_layer.group_add(group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'payload': {
                'event': 'notification.sync',
                'unread_count': await self.get_unread_count(),
                'silent': True,
            },
        }))
        await self.touch_presence(broadcast=False)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            payload = json.loads(text_data or '{}')
        except json.JSONDecodeError:
            return
        if payload.get('action') == 'heartbeat':
            await self.touch_presence()

    async def touch_presence(self, broadcast=True):
        timestamp = await self.save_last_active()
        if not broadcast:
            return
        await self.channel_layer.group_send('labhub_presence', {
            'type': 'realtime.event',
            'payload': {
                'event': 'presence.updated',
                'user_id': self.pengguna.pk,
                'created_at': timestamp,
                'silent': True,
            },
        })

    @database_sync_to_async
    def save_last_active(self):
        now = timezone.now()
        Pengguna.objects.filter(pk=self.pengguna.pk).update(terakhir_aktif_pada=now)
        return now.isoformat()

    async def disconnect(self, close_code):
        for group_name in getattr(self, 'groups', []):
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def realtime_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'payload': event['payload'],
        }))

    @database_sync_to_async
    def get_pengguna(self):
        pengguna_id = self.scope.get('session', {}).get('pengguna_id')
        if not pengguna_id:
            return None
        return Pengguna.objects.filter(pk=pengguna_id, is_verified=True).first()

    @database_sync_to_async
    def get_unread_count(self):
        return Notifikasi.objects.filter(
            pengguna=self.pengguna,
            dibaca_pada__isnull=True,
        ).count()
