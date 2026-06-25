from datetime import datetime, time, timedelta

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.views import PostOnlyDeleteMixin
from apps.ruangan.models import RuanganLab

from .forms import JadwalPraktikumForm
from .models import JadwalPraktikum


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
        return (
            JadwalPraktikum.objects.select_related('ruangan')
            .filter(hari=self.get_selected_hari())
            .order_by('waktu_mulai', 'ruangan__nama', 'mata_kuliah')
        )

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
        context['time_slots'] = self.build_time_slots(list(context['jadwal_list']), ruangan_list)
        return context

    def build_time_slots(self, jadwal_list, ruangan_list):
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
                'cells': [],
            })
            current_dt = next_dt

        cell_map = {}
        occupied = set()
        for jadwal in jadwal_list:
            start_key = self.get_slot_key(jadwal.waktu_mulai, slot_keys)
            if not start_key:
                continue

            start_index = slot_keys.index(start_key)
            selesai = jadwal.waktu_selesai or (datetime.combine(timezone.localdate(), jadwal.waktu_mulai) + timedelta(minutes=30)).time()
            start_dt = datetime.combine(timezone.localdate(), jadwal.waktu_mulai)
            end_dt = datetime.combine(timezone.localdate(), selesai)
            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(minutes=30)

            span = max(1, int((end_dt - start_dt).total_seconds() // 1800))
            span = min(span, len(slot_keys) - start_index)
            cell_map[(start_key, jadwal.ruangan_id)] = {'jadwal': jadwal, 'rowspan': span}

            for offset in range(1, span):
                occupied.add((slot_keys[start_index + offset], jadwal.ruangan_id))

        for slot in slots:
            for ruangan in ruangan_list:
                key = (slot['mulai'].zfill(5), ruangan.pk)
                if key in occupied:
                    continue

                slot['cells'].append({
                    'ruangan': ruangan,
                    'jadwal': cell_map.get(key, {}).get('jadwal'),
                    'rowspan': cell_map.get(key, {}).get('rowspan', 1),
                })

        return slots

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


class JadwalPraktikumCreateView(MahasiswaJadwalReadOnlyMixin, CreateView):
    model = JadwalPraktikum
    form_class = JadwalPraktikumForm
    template_name = 'jadwal/jadwal_form.html'
    success_url = reverse_lazy('jadwal:jadwal_list')


class JadwalPraktikumUpdateView(MahasiswaJadwalReadOnlyMixin, UpdateView):
    model = JadwalPraktikum
    form_class = JadwalPraktikumForm
    template_name = 'jadwal/jadwal_form.html'
    success_url = reverse_lazy('jadwal:jadwal_list')


class JadwalPraktikumDeleteView(MahasiswaJadwalReadOnlyMixin, PostOnlyDeleteMixin, DeleteView):
    model = JadwalPraktikum
    template_name = 'jadwal/jadwal_confirm_delete.html'
    context_object_name = 'jadwal'
    success_url = reverse_lazy('jadwal:jadwal_list')

