import csv

from django.core.management.base import BaseCommand, CommandError

from apps.pengguna.models import School


LEVEL_MAP = {
    'SD': 'SD',
    'MI': 'SD',
    'SMP': 'SMP',
    'MTS': 'SMP',
    'MTSS': 'SMP',
    'SMA': 'SMA',
    'MA': 'SMA',
    'MAS': 'SMA',
    'SMK': 'SMK',
}


class Command(BaseCommand):
    help = 'Import data sekolah dari CSV Data Induk Satuan Pendidikan.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', help='Path file CSV sekolah.')

    def normalize_level(self, row):
        shape = (row.get('Bentuk') or '').strip().upper().replace('.', '')
        if shape in LEVEL_MAP:
            return LEVEL_MAP[shape]
        level_text = (row.get('Jenjang') or '').strip().upper()
        for key, value in LEVEL_MAP.items():
            if key in level_text:
                return value
        return ''

    def normalize_status(self, value):
        normalized = (value or '').strip().lower()
        if 'negeri' in normalized:
            return 'negeri'
        if 'swasta' in normalized:
            return 'swasta'
        return 'lainnya'

    def handle(self, *args, **options):
        path = options['csv_file']
        created = updated = skipped = failed = 0

        try:
            handle = open(path, newline='', encoding='utf-8-sig')
        except OSError as exc:
            raise CommandError(f'File tidak dapat dibuka: {exc}') from exc

        with handle:
            first_line = handle.readline()
            if not first_line.lower().startswith('npsn,'):
                # File dari portal pemerintah sering diawali komentar "# Wilayah::".
                pass
            else:
                handle.seek(0)

            reader = csv.DictReader(handle)
            for line_number, row in enumerate(reader, start=2):
                try:
                    cleaned = {str(key or '').strip(): (value or '').strip() for key, value in row.items()}
                    npsn = cleaned.get('NPSN', '')
                    name = cleaned.get('Nama', '')
                    level = self.normalize_level(cleaned)
                    if not npsn or not name or not level:
                        skipped += 1
                        continue

                    _, was_created = School.objects.update_or_create(
                        npsn=npsn,
                        defaults={
                            'nama': name,
                            'jenjang': level,
                            'status': self.normalize_status(cleaned.get('Status')),
                            'provinsi': cleaned.get('Provinsi', ''),
                            'kabupaten_kota': cleaned.get('Kabupaten', '') or cleaned.get('Kabupaten/Kota', ''),
                            'kecamatan': cleaned.get('Kecamatan', ''),
                            'alamat': cleaned.get('Alamat', ''),
                            'aktif': True,
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                except Exception as exc:  # noqa: BLE001 - command should continue importing other rows.
                    failed += 1
                    self.stderr.write(f'Baris {line_number} gagal: {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'Import selesai. Baru: {created}, diperbarui: {updated}, dilewati: {skipped}, gagal: {failed}.'
        ))
