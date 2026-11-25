from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.kalender.models import Notifikasi
from apps.kalender.realtime import send_user_notification

from .models import Pengguna, PesanPribadi


STIKER = {
    'senang': '😄', 'tertawa': '😂', 'suka': '😍', 'semangat': '💪',
    'sip': '👍', 'terima_kasih': '🙏', 'kaget': '😮', 'sedih': '😢',
}


def conversation_messages(pengguna, target, before_id=None):
    messages = PesanPribadi.objects.filter(
        Q(pengirim=pengguna, penerima=target) | Q(pengirim=target, penerima=pengguna)
    ).select_related('pengirim').order_by('-dibuat_pada', '-pk')
    if before_id:
        messages = messages.filter(pk__lt=before_id)
    return messages[:101]


def chat_target(request, pk):
    return get_object_or_404(Pengguna.objects.exclude(role='admin'), pk=pk, is_verified=True)


def mark_conversation_read(pengguna, target):
    now = timezone.now()
    PesanPribadi.objects.filter(
        pengirim=target, penerima=pengguna, dibaca_pada__isnull=True,
    ).update(dibaca_pada=now)
    Notifikasi.objects.filter(
        pengguna=pengguna, source_key__startswith='chat:',
        url=reverse('pengguna:chat_room', args=[target.pk]), dibaca_pada__isnull=True,
    ).update(dibaca_pada=now)


def touch_presence(pengguna):
    now = timezone.now()
    Pengguna.objects.filter(pk=pengguna.pk).update(terakhir_aktif_pada=now)
    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)('labhub_presence', {
            'type': 'realtime.event',
            'payload': {'event': 'presence.updated', 'user_id': pengguna.pk, 'created_at': now.isoformat(), 'silent': True},
        })


@require_GET
def chat_unread_summary(request):
    pengguna = getattr(request, 'current_pengguna', None)
    if not pengguna:
        return JsonResponse({'detail': 'Login diperlukan.'}, status=403)
    rows = PesanPribadi.objects.filter(
        penerima=pengguna, dibaca_pada__isnull=True,
    ).values('pengirim_id').annotate(total=Count('pk'))
    counts = {str(row['pengirim_id']): row['total'] for row in rows}
    return JsonResponse({'sender_count': len(counts), 'counts': counts})


def create_private_message(pengguna, target, content, sticker=None):
    sticker = str(sticker or '').strip()
    content = str(content or '').strip()
    if sticker:
        if sticker not in STIKER or content:
            return None, 'Stiker tidak valid.', 400
        content = sticker
        jenis = 'stiker'
    else:
        if not content or len(content) > 2000:
            return None, 'Pesan harus berisi 1 sampai 2000 karakter.', 400
        jenis = 'teks'
    if target.pk == pengguna.pk:
        return None, 'Tidak dapat mengirim pesan ke akun sendiri.', 400
    rate_key = f'chat-rate:{pengguna.pk}'
    count = cache.get(rate_key, 0)
    if count >= 30:
        return None, 'Terlalu banyak pesan. Coba lagi sebentar.', 429
    cache.set(rate_key, count + 1, 60)

    with transaction.atomic():
        message = PesanPribadi.objects.create(pengirim=pengguna, penerima=target, isi=content, jenis=jenis)
        url = reverse('pengguna:chat_room', args=[pengguna.pk])
        transaction.on_commit(lambda: send_user_notification(target.pk, {
            'event': 'chat.message',
            'source_key': f'chat:{message.pk}',
            'title': f'Pesan dari {pengguna.nama_pengguna}',
            'message': 'Anda menerima pesan baru.',
            'related_url': url,
            'related_object_id': message.pk,
            'sender_id': pengguna.pk,
            'icon': 'message-circle',
        }))
    return message, None, 201


@require_GET
def chat_room(request, pk):
    pengguna = request.current_pengguna
    target = chat_target(request, pk)
    if target.pk == pengguna.pk:
        return JsonResponse({'detail': 'Tidak dapat mengirim pesan ke akun sendiri.'}, status=400)

    now = timezone.now()
    mark_conversation_read(pengguna, target)
    before_id = request.GET.get('before')
    if before_id and not before_id.isdigit():
        return JsonResponse({'detail': 'Penanda pesan tidak valid.'}, status=400)
    recent = list(conversation_messages(pengguna, target, int(before_id) if before_id else None))
    has_more = len(recent) > 100
    messages = list(reversed(recent[:100]))
    for item in messages:
        item.stiker_emoji = STIKER.get(item.isi) if item.jenis == 'stiker' else None
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({'messages': [
            {
                'id': item.pk,
                'text': item.isi,
                'sticker': item.isi if item.jenis == 'stiker' else None,
                'sticker_emoji': STIKER.get(item.isi) if item.jenis == 'stiker' else None,
                'mine': item.pengirim_id == pengguna.pk,
                'time': timezone.localtime(item.dibuat_pada).strftime('%d %b %H:%M'),
                'read': bool(item.dibaca_pada),
            }
            for item in messages
        ], 'has_more': has_more,
            'online': bool(target.terakhir_aktif_pada and target.terakhir_aktif_pada >= now - timedelta(seconds=75))})
    embedded = request.GET.get('popup') == '1'
    response = render(request, 'pengguna/chat_room.html', {
        'target': target,
        'chat_messages': messages,
        'has_more': has_more,
        'embedded': embedded,
        'stickers': STIKER,
        'online': bool(target.terakhir_aktif_pada and target.terakhir_aktif_pada >= now - timedelta(seconds=75)),
    })
    if embedded:
        response['X-Frame-Options'] = 'SAMEORIGIN'
    return response


@require_POST
def chat_send(request, pk):
    pengguna = request.current_pengguna
    target = chat_target(request, pk)
    message, error, status_code = create_private_message(
        pengguna, target, request.POST.get('message'), request.POST.get('sticker'),
    )
    if error:
        return JsonResponse({'detail': error}, status=status_code)
    return JsonResponse({'ok': True, 'id': message.pk}, status=201)
