from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import PeminjamanAlatForm
from .models import PeminjamanAlat


class PeminjamanAlatListView(ListView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_list.html'
    context_object_name = 'peminjaman_list'


class PeminjamanAlatDetailView(DetailView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_detail.html'
    context_object_name = 'peminjaman'


class PeminjamanAlatCreateView(CreateView):
    model = PeminjamanAlat
    form_class = PeminjamanAlatForm
    template_name = 'peminjaman/peminjaman_form.html'
    success_url = reverse_lazy('peminjaman:peminjaman_list')


class PeminjamanAlatUpdateView(UpdateView):
    model = PeminjamanAlat
    form_class = PeminjamanAlatForm
    template_name = 'peminjaman/peminjaman_form.html'
    success_url = reverse_lazy('peminjaman:peminjaman_list')


class PeminjamanAlatDeleteView(DeleteView):
    model = PeminjamanAlat
    template_name = 'peminjaman/peminjaman_confirm_delete.html'
    context_object_name = 'peminjaman'
    success_url = reverse_lazy('peminjaman:peminjaman_list')

