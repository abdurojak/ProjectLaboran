import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.pengguna.models import Pengguna

from .models import PercakapanBantuan, PesanBantuan
from .realtime import serialize_help_message
from .views import bot_answer


class BantuanChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.percakapan_id = self.scope['url_route']['kwargs']['percakapan_id']
        self.group_name = f'bantuan_{self.percakapan_id}'
        self.pengguna = await self.get_pengguna()
        self.percakapan = await self.get_allowed_conversation()

        if not self.pengguna or not self.percakapan:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = payload.get('action', 'message')
        if action == 'selesai':
            finished = await self.finish_conversation()
            if finished:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'chat.status',
                        'status': 'selesai',
                        'status_label': 'Selesai',
                    },
                )
            return

        content = (payload.get('pesan') or '').strip()[:1000]
        if not content:
            return

        created_messages = await self.create_message(content)
        for message in created_messages:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'chat.message',
                    'message': message,
                },
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def chat_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status',
            'status': event['status'],
            'status_label': event['status_label'],
        }))

    @database_sync_to_async
    def get_pengguna(self):
        pengguna_id = self.scope.get('session', {}).get('pengguna_id')
        if not pengguna_id:
            return None
        try:
            return Pengguna.objects.get(pk=pengguna_id)
        except Pengguna.DoesNotExist:
            return None

    @database_sync_to_async
    def get_allowed_conversation(self):
        try:
            conversation = PercakapanBantuan.objects.select_related('pengguna').get(pk=self.percakapan_id)
        except PercakapanBantuan.DoesNotExist:
            return None

        if self.pengguna.role == 'admin' and conversation.status == 'admin':
            return conversation
        if conversation.pengguna_id == self.pengguna.pk and conversation.status != 'selesai':
            return conversation
        return None

    @database_sync_to_async
    def create_message(self, content):
        conversation = PercakapanBantuan.objects.get(pk=self.percakapan_id)
        sender = 'admin' if self.pengguna.role == 'admin' else 'pengguna'
        message = PesanBantuan.objects.create(
            percakapan=conversation,
            pengirim=sender,
            isi=content,
        )
        messages = [serialize_help_message(message)]

        if sender == 'pengguna' and conversation.status == 'bot':
            bot_message = PesanBantuan.objects.create(
                percakapan=conversation,
                pengirim='bot',
                isi=bot_answer(content),
            )
            messages.append(serialize_help_message(bot_message))

        conversation.save(update_fields=['diperbarui_pada'])
        return messages

    @database_sync_to_async
    def finish_conversation(self):
        if self.pengguna.role != 'admin':
            return False
        conversation = PercakapanBantuan.objects.filter(pk=self.percakapan_id, status='admin').first()
        if not conversation:
            return False
        conversation.status = 'selesai'
        conversation.save(update_fields=['status', 'diperbarui_pada'])
        return True
