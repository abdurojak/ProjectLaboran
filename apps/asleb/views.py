from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import AslebForm
from .models import Asleb


class AslebListView(ListView):
    model = Asleb
    template_name = 'asleb/asleb_list.html'
    context_object_name = 'asleb_list'

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()

        if search:
            queryset = queryset.filter(
                Q(nama__icontains=search) |
                Q(nim__icontains=search) |
                Q(no_hp__icontains=search) |
                Q(program_studi__icontains=search) |
                Q(matkul__icontains=search)
            )

        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '').strip()
        context['selected_status'] = self.request.GET.get('status', '').strip()
        context['status_choices'] = Asleb.STATUS_CHOICES
        return context


class AslebDetailView(DetailView):
    model = Asleb
    template_name = 'asleb/asleb_detail.html'
    context_object_name = 'asleb'


class AslebCreateView(CreateView):
    model = Asleb
    form_class = AslebForm
    template_name = 'asleb/asleb_form.html'
    success_url = reverse_lazy('asleb:asleb_list')


class AslebUpdateView(UpdateView):
    model = Asleb
    form_class = AslebForm
    template_name = 'asleb/asleb_form.html'
    success_url = reverse_lazy('asleb:asleb_list')


class AslebDeleteView(DeleteView):
    model = Asleb
    template_name = 'asleb/asleb_confirm_delete.html'
    context_object_name = 'asleb'
    success_url = reverse_lazy('asleb:asleb_list')
