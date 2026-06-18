from django.views.generic import TemplateView


class RuanganListView(TemplateView):
    template_name = 'ruangan/ruangan_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ruangan_list'] = [
            {
                'nama': 'Lab Rekayasa Perangkat Lunak',
                'kode': 'LAB-RPL',
                'deskripsi': 'Ruang praktik untuk pengembangan aplikasi, pemrograman, dan proyek perangkat lunak.',
                'kapasitas': 20,
                'warna': 'teal',
            },
            {
                'nama': 'Lab Sistem Keamanan Informasi',
                'kode': 'LAB-SKI',
                'deskripsi': 'Ruang praktik untuk simulasi keamanan jaringan, hardening sistem, dan pengujian keamanan.',
                'kapasitas': 18,
                'warna': 'amber',
            },
            {
                'nama': 'Lab Pemrograman',
                'kode': 'LAB-PRG',
                'deskripsi': 'Ruang utama untuk praktikum algoritma, coding dasar, dan eksperimen aplikasi.',
                'kapasitas': 39,
                'warna': 'blue',
            },
            {
                'nama': 'Lab SDA',
                'kode': 'LAB-SDA',
                'deskripsi': 'Ruang untuk praktikum yang berfokus pada sistem digital, analisis data, dan eksperimen komputasi.',
                'kapasitas': 13,
                'warna': 'emerald',
            },
            {
                'nama': 'Lab Rekayasa Data',
                'kode': 'LAB-RD',
                'deskripsi': 'Ruang praktik untuk basis data, pipeline data, dan pemodelan data terapan.',
                'kapasitas': None,
                'warna': 'violet',
            },
        ]
        context['jumlah_ruangan'] = len(context['ruangan_list'])
        return context
