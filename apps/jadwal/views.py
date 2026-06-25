from datetime import datetime, time, timedelta

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.views import PostOnlyDeleteMixin
from apps.pendaftaran_asleb.models import PendaftaranAsleb
from apps.ruangan.models import RuanganLab

from .forms import JadwalPraktikumForm
from .models import JadwalPraktikum


def get_aslab_matkul_labels(pengguna):
    if not pengguna or pengguna.role != 'asisten_lab':
        return []

    matkul_values = PendaftaranAsleb.objects.filter(
        nim=pengguna.nim_nik,
        status__in=['diterima', 'digenerate'],
    ).select_related('matkul').values_list(
        'matkul__nama',
        'matkul__dosen',
        'matkul__kelas',
    )
    return [f'{nama} - {dosen} - {kelas}' for nama, dosen, kelas in matkul_values]


def can_manage_jadwal(pengguna, jadwal):
    if not pengguna:
        return True
    if pengguna.role in ['admin', 'laboran']:
        return True
    if pengguna.role == 'asisten_lab':
        return jadwal.mata_kuliah in get_aslab_matkul_labels(pengguna)
    return False


class MahasiswaJadwalReadOnlyMixin:
    def dispatch(self, request, *args, **kwargs):
        pengguna = getattr(request, 'current_pengguna', None)
        if pengguna and pengguna.role == 'mahasiswa':
            messages.warning(request, 'Mahasiswa hanya dapat melihat jadwal praktikum.')
            return redirect('jadwal:jadwal_list')

        return super().dispatch(request, *args, **kwargs)


class JadwalPraktikumListView(ListView):
    model = JadwalPraktikum
    template_name = 'jadwal/jadwal_list.html'
    context_object_name = 'jadwal_list'
    day_order = [key for key, _ in JadwalPraktikum.HARI_CHOICES]
    day_labels = dict(JadwalPraktikum.HARI_CHOICES)

    def get_selected_hari(self):
        requested_hari = self.request.GET.get('hari', '').strip().lower()
        if requested_hari in self.day_order:
            return requested_hari

        today_index = timezone.localdate().weekday()
        if today_index < len(self.day_order):
            return self.day_order[today_index]

        return 'senin'

    def get_queryset(self):
        queryset = (
            JadwalPraktikum.objects.select_related('ruangan')
            .filter(
                hari=self.get_selected_hari(),
                status=JadwalPraktikum.STATUS_DITERIMA,
            )
            .order_by('waktu_mulai', 'ruangan__nama', 'mata_kuliah')
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_hari = self.get_selected_hari()
        ruangan_list = list(RuanganLab.objects.filter(aktif=True).order_by('nama'))
        context['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        context['hari_tabs'] = [
            {'value': value, 'label': label, 'active': value == selected_hari}
            for value, label in JadwalPraktikum.HARI_CHOICES
        ]
        context['selected_hari'] = selected_hari
        context['selected_hari_label'] = self.day_labels[selected_hari]
        context['ruangan_list'] = ruangan_list
        time_slots, slot_keys = self.build_time_slots()
        context['time_slots'] = time_slots
        context['slot_count'] = len(time_slots)
        context['room_count'] = max(len(ruangan_list), 1)
        context['jadwal_blocks'] = self.build_jadwal_blocks(
            list(context['jadwal_list']),
            ruangan_list,
            slot_keys,
            context['current_pengguna'],
        )
        context['praktikum_saya'] = self.get_praktikum_saya(context['current_pengguna'])
        return context

    def get_praktikum_saya(self, pengguna):
        if not pengguna or pengguna.role != 'asisten_lab':
            return JadwalPraktikum.objects.none()

        labels = get_aslab_matkul_labels(pengguna)
        if not labels:
            return JadwalPraktikum.objects.none()

        return (
            JadwalPraktikum.objects.select_related('ruangan')
            .filter(
                mata_kuliah__in=labels,
                status__in=[JadwalPraktikum.STATUS_DIAJUKAN, JadwalPraktikum.STATUS_DITERIMA],
            )
            .order_by('hari', 'waktu_mulai', 'ruangan__nama', 'mata_kuliah')
        )

    def build_time_slots(self):
        slots = []
        current_dt = datetime.combine(timezone.localdate(), time(7, 30))
        end_dt = datetime.combine(timezone.localdate(), time(18, 0))
        slot_keys = []

        while current_dt < end_dt:
            next_dt = current_dt + timedelta(minutes=30)
            mulai_label = current_dt.strftime('%H:%M')
            slot_keys.append(mulai_label)
            slots.append({
                'mulai': mulai_label.lstrip('0'),
                'selesai': next_dt.strftime('%H:%M').lstrip('0'),
            })
            current_dt = next_dt

        return slots, slot_keys

    def build_jadwal_blocks(self, jadwal_list, ruangan_list, slot_keys, pengguna):
        blocks = []
        ruangan_columns = {ruangan.pk: index + 1 for index, ruangan in enumerate(ruangan_list)}

        for jadwal in jadwal_list:
            start_key = self.get_slot_key(jadwal.waktu_mulai, slot_keys)
            grid_column = ruangan_columns.get(jadwal.ruangan_id)
            if not start_key or not grid_column:
                continue

            start_index = slot_keys.index(start_key)
            selesai = jadwal.waktu_selesai or (datetime.combine(timezone.localdate(), jadwal.waktu_mulai) + timedelta(minutes=30)).time()
            start_dt = datetime.combine(timezone.localdate(), jadwal.waktu_mulai)
            end_dt = datetime.combine(timezone.localdate(), selesai)
            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(minutes=30)

            span = max(1, int((end_dt - start_dt).total_seconds() // 1800))
            span = min(span, len(slot_keys) - start_index)
            blocks.append({
                'jadwal': jadwal,
                'grid_column': grid_column,
                'grid_row': start_index + 1,
                'span': span,
                'can_manage': can_manage_jadwal(pengguna, jadwal),
            })

        return blocks

    def get_slot_key(self, value, slot_keys):
        value_dt = datetime.combine(timezone.localdate(), value)
        selected_key = None

        for slot_key in slot_keys:
            slot_dt = datetime.combine(timezone.localdate(), datetime.strptime(slot_key, '%H:%M').time())
            if slot_dt <= value_dt:
                selected_key = slot_key
            else:
                break

        return selected_key


class JadwalPraktikumDetailView(DetailView):
    model = JadwalPraktikum
    template_name = 'jadwal/jadwal_detail.html'
    context_object_name = 'jadwal'

    def get_queryset(self):
        queryset = super().get_queryset()
        pengguna = getattr(self.request, 'current_pengguna', None)
        if pengguna and pengguna.role == 'mahasiswa':
            return queryset.filter(status=JadwalPraktikum.STATUS_DITERIMA)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        context['can_manage_jadwal'] = can_manage_jadwal(context['current_pengguna'], self.object)
        return context


class JadwalPraktikumCreateView(MahasiswaJadwalReadOnlyMixin, CreateView):
    model = JadwalPraktikum
    form_class = JadwalPraktikumForm
    template_name = 'jadwal/jadwal_form.html'
    success_url = reverse_lazy('jadwal:jadwal_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs


class JadwalPraktikumUpdateView(MahasiswaJadwalReadOnlyMixin, UpdateView):
    model = JadwalPraktikum
    form_class = JadwalPraktikumForm
    template_name = 'jadwal/jadwal_form.html'
    success_url = reverse_lazy('jadwal:jadwal_list')

    def get_queryset(self):
        queryset = super().get_queryset()
        pengguna = getattr(self.request, 'current_pengguna', None)
        if pengguna and pengguna.role == 'asisten_lab':
            return queryset.filter(mata_kuliah__in=get_aslab_matkul_labels(pengguna))
        return queryset

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_pengguna'] = getattr(self.request, 'current_pengguna', None)
        return kwargs


class JadwalPraktikumDeleteView(MahasiswaJadwalReadOnlyMixin, PostOnlyDeleteMixin, DeleteView):
    model = JadwalPraktikum
    template_name = 'jadwal/jadwal_confirm_delete.html'
    context_object_name = 'jadwal'
    success_url = reverse_lazy('jadwal:jadwal_list')

    def get_queryset(self):
        queryset = super().get_queryset()
        pengguna = getattr(self.request, 'current_pengguna', None)
        if pengguna and pengguna.role == 'asisten_lab':
            return queryset.filter(mata_kuliah__in=get_aslab_matkul_labels(pengguna))
        return queryset

