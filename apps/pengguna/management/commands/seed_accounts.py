from django.core.management.base import BaseCommand

from apps.pengguna.models import Pengguna


DEFAULT_PASSWORDS = {
    'admin': 'admin12345',
    'laboran': 'laboran12345',
    'asisten_lab': 'asistenlab12345',
    'mahasiswa': 'mahasiswa12345',
}


ACCOUNTS = [
    {
        'role': 'admin',
        'nama_pengguna': 'Admin LabHub',
        'nim_nik': '1000000001',
        'email': 'admin@trisakti.ac.id',
        'no_hp': '081200000001',
        'alamat': 'Universitas Trisakti',
        'fakultas': 'Teknologi Industri',
        'prodi': 'Informatika',
        'gender': 'laki_laki',
    },
    {
        'role': 'laboran',
        'nama_pengguna': 'Laboran LabHub',
        'nim_nik': '1000000002',
        'email': 'laboran@trisakti.ac.id',
        'no_hp': '081200000002',
        'alamat': 'Universitas Trisakti',
        'fakultas': 'Teknologi Industri',
        'prodi': 'Informatika',
        'gender': 'laki_laki',
    },
    {
        'role': 'mahasiswa',
        'nama_pengguna': 'Mahasiswa LabHub',
        'nim_nik': '1000000003',
        'email': 'mahasiswa@std.trisakti.ac.id',
        'no_hp': '081200000003',
        'alamat': 'Universitas Trisakti',
        'fakultas': 'Teknologi Industri',
        'prodi': 'Informatika',
        'gender': 'laki_laki',
    },
    {
        'role': 'asisten_lab',
        'nama_pengguna': 'Asisten Lab LabHub',
        'nim_nik': '1000000004',
        'email': 'asistenlab@std.trisakti.ac.id',
        'no_hp': '081200000004',
        'alamat': 'Universitas Trisakti',
        'fakultas': 'Teknologi Industri',
        'prodi': 'Informatika',
        'gender': 'laki_laki',
    },
]


class Command(BaseCommand):
    help = 'Create or update default accounts for every application role.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            default=None,
            help='Use one password for all seeded accounts. Defaults to role-specific passwords.',
        )

    def handle(self, *args, **options):
        shared_password = options['password']

        for account in ACCOUNTS:
            password = shared_password or DEFAULT_PASSWORDS[account['role']]
            pengguna, created = Pengguna.objects.update_or_create(
                nim_nik=account['nim_nik'],
                defaults={
                    **account,
                    'password': password,
                    'is_verified': True,
                },
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(
                self.style.SUCCESS(
                    f'{action} {pengguna.role}: {pengguna.nim_nik} / {password}'
                )
            )
