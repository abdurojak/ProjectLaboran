from django.views.generic import TemplateView


class BarangTertinggalListView(TemplateView):
    template_name = 'barang_tertinggal/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['barang_tertinggal_list'] = []
        return context

