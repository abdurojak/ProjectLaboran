from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone


def serialize_help_message(pesan):
    return {
        'id': pesan.pk,
        'pengirim': pesan.pengirim,
        'pengirim_label': pesan.get_pengirim_display(),
        'isi': pesan.isi,
        'dibuat_pada': timezone.localtime(pesan.dibuat_pada).strftime('%d %b %Y %H:%M'),
    }


def broadcast_help_message(pesan):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        f'bantuan_{pesan.percakapan_id}',
        {
            'type': 'chat.message',
            'message': serialize_help_message(pesan),
        },
    )


def broadcast_help_status(percakapan):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        f'bantuan_{percakapan.pk}',
        {
            'type': 'chat.status',
            'status': percakapan.status,
            'status_label': percakapan.get_status_display(),
        },
    )
