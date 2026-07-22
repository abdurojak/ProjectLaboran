from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from apps.asleb.models import Asleb
from apps.pendaftaran_asleb.models import AslabAssignment, PendaftaranAsleb


ACCEPTED_STATUSES = ('diterima', 'digenerate')


def matching_registration(asleb):
    candidates = list(
        PendaftaranAsleb.objects.filter(
            nim=asleb.nim,
            periode_id=asleb.periode_aktif_id,
            status__in=ACCEPTED_STATUSES,
        ).select_related('matkul').order_by('pk')
    )
    if len(candidates) == 1:
        return candidates[0], None
    if len(candidates) > 1 and asleb.matkul:
        exact = [item for item in candidates if str(item.matkul) == asleb.matkul]
        if len(exact) == 1:
            return exact[0], None
    return (None, 'UNMATCHED') if not candidates else (None, 'AMBIGUOUS')


class Command(BaseCommand):
    help = 'Audit legacy active Aslab rows and assignment slot occupancy without modifying data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict',
            action='store_true',
            help='Exit nonzero when any active legacy Aslab row is unresolved.',
        )

    def handle(self, *args, **options):
        categories = defaultdict(list)
        active_aslebs = Asleb.objects.filter(status='aktif').order_by('pk')

        for asleb in active_aslebs:
            if asleb.periode_aktif_id is None:
                categories['NO_PERIOD'].append(asleb.nim)
                continue
            registration, match_issue = matching_registration(asleb)
            if match_issue:
                categories[match_issue].append(asleb.nim)
                continue

            assignments = list(
                AslabAssignment.objects.filter(asleb=asleb, status='active')
                .select_related('slot', 'source_pendaftaran__matkul')
                .order_by('pk')
            )
            if not assignments:
                occupied = AslabAssignment.objects.filter(
                    slot__periode=asleb.periode_aktif,
                    slot__matkul=registration.matkul,
                    status='active',
                ).values('slot__nomor').distinct().count()
                category = 'OVER_CAPACITY' if occupied >= 2 else 'MISSING_ASSIGNMENT'
                categories[category].append(asleb.nim)
                continue

            if len(assignments) != 1:
                categories['INCONSISTENT_OCCUPANCY'].append(
                    f'{asleb.nim} has {len(assignments)} active assignments'
                )
            for assignment in assignments:
                if (
                    assignment.active_slot_id != assignment.slot_id
                    or assignment.slot.status != 'active'
                    or assignment.slot.periode_id != asleb.periode_aktif_id
                    or assignment.slot.matkul_id != registration.matkul_id
                    or assignment.source_pendaftaran_id != registration.pk
                ):
                    categories['INCONSISTENT_OCCUPANCY'].append(
                        f'{asleb.nim} assignment {assignment.pk} has mismatched guard/source/slot'
                    )

        occupancy = defaultdict(list)
        for assignment in AslabAssignment.objects.filter(status='active').order_by('pk'):
            occupancy[assignment.slot_id].append(assignment.pk)
        for slot_id, assignment_ids in occupancy.items():
            if len(assignment_ids) > 1:
                categories['DUPLICATE_OCCUPANCY'].append(
                    f'slot {slot_id} assignments {assignment_ids}'
                )

        ordered_categories = (
            'NO_PERIOD',
            'AMBIGUOUS',
            'UNMATCHED',
            'OVER_CAPACITY',
            'MISSING_ASSIGNMENT',
            'DUPLICATE_OCCUPANCY',
            'INCONSISTENT_OCCUPANCY',
        )
        for category in ordered_categories:
            values = categories[category]
            if values:
                self.stdout.write(f'{category}: {", ".join(values)}')
        if not any(categories.values()):
            self.stdout.write('OK: no unresolved active legacy rows or occupancy issues')

        unresolved = sum(
            len(categories[name])
            for name in ('NO_PERIOD', 'AMBIGUOUS', 'UNMATCHED', 'OVER_CAPACITY', 'MISSING_ASSIGNMENT')
        )
        if options['strict'] and unresolved:
            raise CommandError(f'{unresolved} active legacy Aslab row(s) unresolved')
