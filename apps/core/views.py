import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from .bot_knowledge import BOT_FALLBACK, BOT_GUIDE_TOPICS, BOT_GUIDE_INTRO
from apps.pengguna.forms import PenggunaAppearanceForm

from .models import BugErrorLog, PercakapanBantuan, PesanBantuan
from .realtime import broadcast_help_message, broadcast_help_status


def fallback_bot_answer(question):
    normalized = question.lower()
    if any(keyword in normalized for keyword in {'panduan', 'fitur web', 'fitur labhub', 'apa saja', 'bisa apa'}):
        return (
            f'{BOT_GUIDE_INTRO}\n\n'
            'Topik yang bisa saya bantu: login/registrasi, role dan hak akses, pendaftaran asleb, absensi asleb, '
            'nilai dan absensi mahasiswa, peserta praktikum CSV, inventaris dan peminjaman, kalender, profil/CV, honorarium, notifikasi, '
            'pengaturan, dan aplikasi mobile absensi.'
        )
    for topic in BOT_GUIDE_TOPICS:
        if any(keyword in normalized for keyword in topic['keywords']):
            return topic['answer']
    return BOT_FALLBACK


def openai_bot_answer(question):
    if not settings.OPENAI_API_KEY:
        return ''

    topic_context = '\n\n'.join(
        f"- Kata kunci: {', '.join(sorted(topic['keywords']))}\n  Jawaban panduan: {topic['answer']}"
        for topic in BOT_GUIDE_TOPICS
    )
    payload = {
        'model': settings.OPENAI_CHATBOT_MODEL,
        'input': [
            {
                'role': 'system',
                'content': (
                    'Anda adalah chatbot bantuan LabHub/Project Laboran. Jawab dalam Bahasa Indonesia yang singkat, ramah, '
                    'dan praktis. Utamakan panduan internal berikut. Jika pertanyaan di luar sistem, arahkan pengguna untuk '
                    'menghubungi admin. Jangan mengarang fitur yang tidak ada.\n\n'
                    f'{BOT_GUIDE_INTRO}\n\n{topic_context}'
                ),
            },
            {'role': 'user', 'content': question},
        ],
        'temperature': 0.2,
        'max_output_tokens': 450,
    }
    request = Request(
        'https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {settings.OPENAI_API_KEY}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=settings.OPENAI_CHATBOT_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return ''

    text = (data.get('output_text') or '').strip()
    if text:
        return text

    for output in data.get('output', []):
        for content in output.get('content', []):
            if content.get('type') in {'output_text', 'text'} and content.get('text'):
                return content['text'].strip()
    return ''


def bot_answer(question):
    return openai_bot_answer(question) or fallback_bot_answer(question)


def get_active_help_conversation(pengguna):
    conversation = pengguna.percakapan_bantuan.exclude(status='selesai').first()
    if conversation:
        return conversation
    conversation = PercakapanBantuan.objects.create(pengguna=pengguna)
    PesanBantuan.objects.create(
        percakapan=conversation,
        pengirim='bot',
        isi=f'{BOT_GUIDE_INTRO} Silakan tanyakan cara menggunakan fitur aplikasi.',
    )
    return conversation


class PostOnlyDeleteMixin:
    def get(self, request, *args, **kwargs):
        if getattr(self, 'success_url', None):
            return redirect(self.success_url)
        return redirect(self.get_success_url())


class SettingsView(TemplateView):
    template_name = 'core/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pengguna = getattr(self.request, 'current_pengguna', None)
        context['pengguna'] = pengguna
        context['settings_cards'] = self.get_settings_cards(pengguna)
        context['appearance_form'] = kwargs.get('appearance_form') or PenggunaAppearanceForm(instance=pengguna)
        return context

    def post(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna:
            return redirect('pengguna:login')

        form = PenggunaAppearanceForm(request.POST, request.FILES, instance=pengguna)
        if form.is_valid():
            form.save()
            request.current_pengguna = pengguna
            return redirect('core:settings')

        return self.render_to_response(self.get_context_data(appearance_form=form))

    def get_settings_cards(self, pengguna):
        if not pengguna:
            return []

        cards = [
            {
                'title': 'Profil Saya',
                'description': 'Lihat dan perbarui identitas akun yang sedang digunakan.',
                'url': 'pengguna:detail',
                'args': [pengguna.pk],
                'icon': 'user-round',
            },
            {
                'title': 'Ganti Password',
                'description': 'Ubah password akun agar akses tetap aman.',
                'url': 'pengguna:detail',
                'args': [pengguna.pk],
                'icon': 'key-round',
            },
        ]

        if pengguna.role != 'admin':
            cards.insert(0, {
                'title': 'Bantuan',
                'description': 'Tanyakan penggunaan aplikasi ke bot atau teruskan percakapan ke admin.',
                'url': 'core:bantuan',
                'args': [],
                'icon': 'message-circle-question',
            })

        if pengguna.role in {'admin', 'laboran'}:
            cards.append({
                'title': 'Pengguna',
                'description': 'Lihat akun dan data pengguna sistem.',
                'url': 'pengguna:list',
                'args': [],
                'icon': 'users',
            })

        if pengguna.role == 'laboran':
            cards.append({
                'title': 'Bug & Error List',
                'description': 'Ambil dan pantau bug/error yang sedang ditangani laboran.',
                'url': 'core:bug_error_list',
                'args': [],
                'icon': 'bug',
            })

        if pengguna.role == 'admin':
            cards.extend([
                {
                    'title': 'Chat Bantuan Masuk',
                    'description': 'Balas pertanyaan pengguna yang diteruskan dari bot bantuan.',
                    'url': 'core:bantuan_admin',
                    'args': [],
                    'icon': 'messages-square',
                },
                {
                    'title': 'Bug & Error List',
                    'description': 'Catat dan pantau daftar bug/error aplikasi secara manual.',
                    'url': 'core:bug_error_list',
                    'args': [],
                    'icon': 'bug',
                },
                {
                    'title': 'Master Akademik',
                    'description': 'Kelola fakultas dan prodi yang muncul pada registrasi.',
                    'url': 'pengguna:master_akademik',
                    'args': [],
                    'icon': 'graduation-cap',
                },
            ])

        for card in cards:
            card['href'] = reverse(card['url'], args=card.get('args', []))
        return cards


class BantuanView(TemplateView):
    template_name = 'core/bantuan.html'

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request, 'current_pengguna', None):
            return redirect('pengguna:login')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['percakapan'] = get_active_help_conversation(self.request.current_pengguna)
        return context

    def post(self, request, *args, **kwargs):
        conversation = get_active_help_conversation(request.current_pengguna)
        content = request.POST.get('pesan', '').strip()[:1000]
        if not content:
            messages.error(request, 'Tulis pertanyaan terlebih dahulu.')
            return redirect('core:bantuan')

        user_message = PesanBantuan.objects.create(percakapan=conversation, pengirim='pengguna', isi=content)
        broadcast_help_message(user_message)
        if conversation.status == 'bot':
            bot_message = PesanBantuan.objects.create(percakapan=conversation, pengirim='bot', isi=bot_answer(content))
            broadcast_help_message(bot_message)
        conversation.save(update_fields=['diperbarui_pada'])
        return redirect('core:bantuan')


class BantuanAsyncMessageView(View):
    def post(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna:
            return JsonResponse({'error': 'Silakan login terlebih dahulu.'}, status=401)

        conversation = get_active_help_conversation(pengguna)
        content = request.POST.get('pesan', '').strip()[:1000]
        if not content:
            return JsonResponse({'error': 'Tulis pertanyaan terlebih dahulu.'}, status=400)

        user_message = PesanBantuan.objects.create(percakapan=conversation, pengirim='pengguna', isi=content)
        broadcast_help_message(user_message)
        bot_message = None
        if conversation.status == 'bot':
            bot_message = PesanBantuan.objects.create(percakapan=conversation, pengirim='bot', isi=bot_answer(content))
            broadcast_help_message(bot_message)
        conversation.save(update_fields=['diperbarui_pada'])

        return JsonResponse({
            'conversation_status': conversation.status,
            'help_url': reverse('core:bantuan'),
            'user_message': {
                'sender': user_message.get_pengirim_display(),
                'content': user_message.isi,
                'created_at': timezone.localtime(user_message.dibuat_pada).strftime('%H:%M'),
            },
            'bot_message': {
                'sender': bot_message.get_pengirim_display(),
                'content': bot_message.isi,
                'created_at': timezone.localtime(bot_message.dibuat_pada).strftime('%H:%M'),
            } if bot_message else None,
            'notice': None if bot_message else 'Percakapan sudah diteruskan ke admin. Pesan Anda tersimpan di halaman bantuan.',
        })


class EskalasiBantuanView(View):
    def post(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna:
            return redirect('pengguna:login')
        conversation = get_active_help_conversation(pengguna)
        if conversation.status == 'bot':
            conversation.status = 'admin'
            conversation.save(update_fields=['status', 'diperbarui_pada'])
            broadcast_help_status(conversation)
            message = PesanBantuan.objects.create(
                percakapan=conversation,
                pengirim='bot',
                isi='Pertanyaan Anda sudah diteruskan ke admin. Silakan tunggu balasan pada halaman ini.',
            )
            broadcast_help_message(message)
        return redirect('core:bantuan')


class AdminBantuanView(TemplateView):
    template_name = 'core/bantuan_admin.html'

    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role != 'admin':
            messages.error(request, 'Hanya admin yang dapat membuka antrean bantuan.')
            return redirect('core:bantuan')
        return super().dispatch(request, *args, **kwargs)

    def get_selected(self):
        conversations = PercakapanBantuan.objects.filter(status='admin').select_related('pengguna')
        selected_id = self.request.GET.get('percakapan') or self.request.POST.get('percakapan')
        if selected_id:
            return get_object_or_404(conversations, pk=selected_id)
        return conversations.first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['percakapan_list'] = PercakapanBantuan.objects.filter(status='admin').select_related('pengguna')
        context['percakapan'] = self.get_selected()
        return context

    def post(self, request, *args, **kwargs):
        conversation = self.get_selected()
        if not conversation:
            return redirect('core:bantuan_admin')
        if request.POST.get('action') == 'selesai':
            conversation.status = 'selesai'
            conversation.save(update_fields=['status', 'diperbarui_pada'])
            broadcast_help_status(conversation)
            messages.success(request, 'Percakapan bantuan ditandai selesai.')
            return redirect('core:bantuan_admin')

        content = request.POST.get('pesan', '').strip()[:1000]
        if content:
            admin_message = PesanBantuan.objects.create(percakapan=conversation, pengirim='admin', isi=content)
            conversation.save(update_fields=['diperbarui_pada'])
            broadcast_help_message(admin_message)
        return redirect(f"{reverse('core:bantuan_admin')}?percakapan={conversation.pk}")


class AdminBantuanSummaryView(View):
    def get(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role != 'admin':
            return JsonResponse({'error': 'Hanya admin yang dapat membuka ringkasan bantuan.'}, status=403)
        waiting_count = PercakapanBantuan.objects.filter(status='admin').count()
        return JsonResponse({
            'waiting_count': waiting_count,
            'label': f'{waiting_count} mahasiswa bertanya',
        })


class BugErrorListView(TemplateView):
    template_name = 'core/bug_error_list.html'
    partial_template_name = 'core/partials/bug_error_content.html'

    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if not pengguna or pengguna.role not in {'admin', 'laboran'}:
            messages.error(request, 'Hanya admin dan laboran yang dapat membuka Bug & Error List.')
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        if self.request.headers.get('HX-Request') == 'true':
            return [self.partial_template_name]
        return [self.template_name]

    def get_queryset(self):
        queryset = BugErrorLog.objects.select_related('dilaporkan_oleh', 'ditangani_oleh')
        status = self.request.GET.get('status', '').strip()
        q = self.request.GET.get('q', '').strip()
        if status in dict(BugErrorLog.STATUS_CHOICES):
            queryset = queryset.filter(status=status)
        if q:
            queryset = queryset.filter(
                Q(judul__icontains=q) |
                Q(lokasi__icontains=q) |
                Q(deskripsi__icontains=q)
            )
        return queryset.order_by('-dibuat_pada')

    def get_selected(self, queryset):
        selected_id = self.request.GET.get('log')
        if selected_id:
            return get_object_or_404(queryset, pk=selected_id)
        return queryset.first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        context['status_choices'] = BugErrorLog.STATUS_CHOICES
        context['kategori_choices'] = BugErrorLog.KATEGORI_CHOICES
        context['prioritas_choices'] = BugErrorLog.PRIORITAS_CHOICES
        context['can_manage_bug_error'] = self.request.current_pengguna.role == 'admin'
        context['can_claim_bug_error'] = self.request.current_pengguna.role == 'laboran'
        context['current_status'] = self.request.GET.get('status', '').strip()
        context['current_q'] = self.request.GET.get('q', '').strip()
        context['bug_error_list'] = queryset[:80]
        context['selected_log'] = self.get_selected(queryset)
        context['can_complete_selected_bug_error'] = (
            self.request.current_pengguna.role == 'laboran'
            and context['selected_log']
            and context['selected_log'].ditangani_oleh_id == self.request.current_pengguna.pk
            and context['selected_log'].status != BugErrorLog.STATUS_SELESAI
        )
        context['summary'] = {
            'baru': BugErrorLog.objects.filter(status=BugErrorLog.STATUS_BARU).count(),
            'diproses': BugErrorLog.objects.filter(status=BugErrorLog.STATUS_DIPROSES).count(),
            'selesai': BugErrorLog.objects.filter(status=BugErrorLog.STATUS_SELESAI).count(),
        }
        return context

    def post(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        action = request.POST.get('action')

        if action == 'claim':
            if not pengguna or pengguna.role != 'laboran':
                messages.error(request, 'Hanya laboran yang dapat mengambil bug/error.')
                return redirect('core:bug_error_list')
            log = get_object_or_404(BugErrorLog, pk=request.POST.get('log_id'))
            updated = BugErrorLog.objects.filter(pk=log.pk, ditangani_oleh__isnull=True).update(
                ditangani_oleh=pengguna,
                status=BugErrorLog.STATUS_DIPROSES,
                diperbarui_pada=timezone.now(),
            )
            if updated:
                messages.success(request, 'Bug/error berhasil diambil dan status diubah menjadi Diproses.')
            else:
                messages.error(request, 'Bug/error ini sudah diambil oleh laboran lain.')
            return redirect(f"{reverse('core:bug_error_list')}?log={log.pk}")

        if action == 'complete':
            if not pengguna or pengguna.role != 'laboran':
                messages.error(request, 'Hanya laboran yang menangani bug/error ini yang dapat menyelesaikannya.')
                return redirect('core:bug_error_list')
            log = get_object_or_404(BugErrorLog, pk=request.POST.get('log_id'))
            updated = BugErrorLog.objects.filter(pk=log.pk, ditangani_oleh=pengguna).exclude(
                status=BugErrorLog.STATUS_SELESAI,
            ).update(
                status=BugErrorLog.STATUS_SELESAI,
                diperbarui_pada=timezone.now(),
            )
            if updated:
                messages.success(request, 'Bug/error berhasil ditandai selesai.')
            else:
                messages.error(request, 'Bug/error ini hanya dapat diselesaikan oleh laboran yang sedang menanganinya.')
            return redirect(f"{reverse('core:bug_error_list')}?log={log.pk}")

        if not pengguna or pengguna.role != 'admin':
            messages.error(request, 'Hanya admin yang dapat mengubah data Bug & Error List.')
            return redirect('core:bug_error_list')

        if action == 'create':
            title = request.POST.get('judul', '').strip()
            description = request.POST.get('deskripsi', '').strip()
            if not title or not description:
                messages.error(request, 'Judul dan deskripsi wajib diisi.')
                return redirect('core:bug_error_list')
            category = request.POST.get('kategori', BugErrorLog.KATEGORI_BUG)
            priority = request.POST.get('prioritas', BugErrorLog.PRIORITAS_SEDANG)
            log = BugErrorLog.objects.create(
                judul=title,
                kategori=category if category in dict(BugErrorLog.KATEGORI_CHOICES) else BugErrorLog.KATEGORI_BUG,
                prioritas=priority if priority in dict(BugErrorLog.PRIORITAS_CHOICES) else BugErrorLog.PRIORITAS_SEDANG,
                lokasi=request.POST.get('lokasi', '').strip(),
                deskripsi=description,
                langkah_reproduksi=request.POST.get('langkah_reproduksi', '').strip(),
                ekspektasi=request.POST.get('ekspektasi', '').strip(),
                hasil_aktual=request.POST.get('hasil_aktual', '').strip(),
                dilaporkan_oleh=getattr(request, 'current_pengguna', None),
            )
            messages.success(request, 'Bug/error berhasil ditambahkan.')
            return redirect(f"{reverse('core:bug_error_list')}?log={log.pk}")

        log = get_object_or_404(BugErrorLog, pk=request.POST.get('log_id'))
        if action == 'delete':
            log.delete()
            messages.success(request, 'Bug/error berhasil dihapus.')
            return redirect('core:bug_error_list')

        status = request.POST.get('status', '').strip()
        if status in dict(BugErrorLog.STATUS_CHOICES):
            log.status = status
            log.catatan_admin = request.POST.get('catatan_admin', '').strip()
            log.save(update_fields=['status', 'catatan_admin', 'diperbarui_pada'])
            messages.success(request, 'Status bug/error berhasil diperbarui.')
        else:
            messages.error(request, 'Status bug/error tidak valid.')
        return redirect(f"{reverse('core:bug_error_list')}?log={log.pk}")
