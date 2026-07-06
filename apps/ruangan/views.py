from django.views.generic import ListView

from .models import GrupRuanganGabungan, RuanganLab


class RuanganListView(ListView):
    model = RuanganLab
    template_name = 'ruangan/ruangan_list.html'
    context_object_name = 'ruangan_list'

    def get_queryset(self):
        return RuanganLab.objects.filter(aktif=True).order_by('nama')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['jumlah_ruangan'] = context['ruangan_list'].count()
        context['grup_gabungan_list'] = (
            GrupRuanganGabungan.objects.filter(aktif=True)
            .prefetch_related('ruangan')
            .order_by('nama')
        )
        return context
