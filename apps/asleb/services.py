from .models import PesertaPraktikum


def get_active_asleb_for_pengguna(pengguna):
    """Resolve the currently active Aslab profile for an authenticated user."""
    if not pengguna or getattr(pengguna, 'role', '') != 'asisten_lab':
        return None

    from .models import Asleb

    return (
        Asleb.objects.filter(
            nim=getattr(pengguna, 'nim_nik', ''),
            status='aktif',
        )
        .order_by('-diperbarui_pada', '-pk')
        .first()
    )


def get_active_asleb_matkul_ids(asleb):
    """Return every course currently assigned to an active Aslab profile.

    AslabAssignment is the authoritative source for current periods. The
    legacy fallbacks keep older generated records usable while they are being
    migrated to assignment slots.
    """
    if not asleb or asleb.status != 'aktif':
        return set()

    from apps.pendaftaran_asleb.models import AslabAssignment, MataKuliahAsleb, PendaftaranAsleb

    assignment_ids = set(
        AslabAssignment.objects.filter(
            asleb=asleb,
            status=AslabAssignment.STATUS_ACTIVE,
        ).values_list('slot__matkul_id', flat=True)
    )
    if assignment_ids:
        return assignment_ids

    legacy_match = MataKuliahAsleb.objects.filter(
        aktif=True,
    ).filter(
        nama__isnull=False,
    )
    legacy_id = next(
        (matkul.pk for matkul in legacy_match if str(matkul) == asleb.matkul),
        None,
    )
    if legacy_id:
        return {legacy_id}

    registration_matkul_id = (
        PendaftaranAsleb.objects.filter(
            nim=asleb.nim,
            status='digenerate',
        )
        .order_by('-pk')
        .values_list('matkul_id', flat=True)
        .first()
    )
    return {registration_matkul_id} if registration_matkul_id else set()


def get_active_asleb_period(asleb):
    """Resolve the period that owns new operational records for an Aslab."""
    if not asleb or asleb.status != 'aktif':
        return None

    from apps.pendaftaran_asleb.models import AslabAssignment

    assignment_period = (
        AslabAssignment.objects.filter(
            asleb=asleb,
            status=AslabAssignment.STATUS_ACTIVE,
        )
        .select_related('slot__periode')
        .order_by('-mulai_pada', '-pk')
        .values_list('slot__periode_id', flat=True)
        .first()
    )
    if assignment_period:
        from apps.pendaftaran_asleb.models import PeriodeAsleb

        return PeriodeAsleb.objects.filter(pk=assignment_period).first()
    return asleb.periode_aktif


def get_active_asleb_matkul_ids_for_pengguna(pengguna):
    """Return course IDs from the active assignment owned by ``pengguna``."""
    return get_active_asleb_matkul_ids(get_active_asleb_for_pengguna(pengguna))


def get_active_asleb_matkul_labels(pengguna):
    """Return canonical schedule labels for every currently assigned course."""
    from apps.pendaftaran_asleb.models import MataKuliahAsleb

    matkul_ids = get_active_asleb_matkul_ids_for_pengguna(pengguna)
    if not matkul_ids:
        return []
    return [
        str(matkul)
        for matkul in MataKuliahAsleb.objects.filter(
            pk__in=matkul_ids,
            aktif=True,
        ).order_by('nama', 'kelas', 'pk')
    ]


def get_active_asleb_matkul(asleb):
    """Return a deterministic primary course for legacy single-course callers."""
    from apps.pendaftaran_asleb.models import MataKuliahAsleb

    matkul_ids = get_active_asleb_matkul_ids(asleb)
    if not matkul_ids:
        return None

    preferred = next(
        (
            matkul
            for matkul in MataKuliahAsleb.objects.filter(pk__in=matkul_ids, aktif=True)
            if str(matkul) == asleb.matkul
        ),
        None,
    )
    if preferred:
        return preferred
    return MataKuliahAsleb.objects.filter(pk__in=matkul_ids, aktif=True).order_by('pk').first()


def get_asleb_matkul_for_schedule(asleb, jadwal):
    """Resolve the assigned course represented by a schedule label."""
    if not jadwal:
        return None

    from apps.pendaftaran_asleb.models import MataKuliahAsleb

    return next(
        (
            matkul
            for matkul in MataKuliahAsleb.objects.filter(
                pk__in=get_active_asleb_matkul_ids(asleb),
                aktif=True,
            )
            if str(matkul) == jadwal.mata_kuliah
        ),
        None,
    )


def link_peserta_praktikum_to_pengguna(pengguna):
    if not pengguna or not getattr(pengguna, 'nim_nik', None):
        return 0
    nim = pengguna.nim_nik.strip()
    if not nim:
        return 0
    return PesertaPraktikum.objects.filter(
        nim=nim,
        pengguna__isnull=True,
    ).update(pengguna=pengguna)
