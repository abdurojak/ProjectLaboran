from io import BytesIO
from secrets import token_urlsafe

import qrcode
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.core.permissions import ASISTEN_LAB_ROLE, MAHASISWA_ROLE
from apps.kalender.realtime import send_data_refresh
from apps.pengguna.models import Pengguna

from .models import HasilPraktikumMahasiswa, ModulPraktikum, PesertaPraktikum


QR_SALT = 'praktikum-mahasiswa-qr-v1'
QR_MAX_AGE_SECONDS = 60


def issue_student_token(pengguna):
    return signing.dumps({
        'user': pengguna.pk, 'nim': pengguna.nim_nik, 'nonce': token_urlsafe(12),
    }, salt=QR_SALT)


def _student(request):
    pengguna = getattr(request, 'current_pengguna', None)
    if pengguna and pengguna.role in {MAHASISWA_ROLE, ASISTEN_LAB_ROLE}:
        return pengguna
    return None


def _active_participants(pengguna):
    return PesertaPraktikum.objects.filter(
        nim=pengguna.nim_nik, aktif=True, matkul__aktif=True,
    ).filter(Q(pengguna__isnull=True) | Q(pengguna=pengguna))


@never_cache
@require_GET
def student_qr_page(request):
    pengguna = _student(request)
    if not pengguna:
        return HttpResponse(status=403)
    return render(request, 'asleb/qr_mahasiswa.html', {
        'pengguna': pengguna,
        'kelas': _active_participants(pengguna).select_related('matkul').order_by('matkul__nama', 'matkul__kelas'),
    })


@never_cache
@require_GET
def student_qr_image(request):
    pengguna = _student(request)
    if not pengguna:
        return HttpResponse(status=403)
    if not _active_participants(pengguna).exists():
        return HttpResponse(status=404)
    token = issue_student_token(pengguna)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=3)
    qr.add_data(token)
    qr.make(fit=True)
    output = BytesIO()
    qr.make_image(fill_color='#103b42', back_color='white').save(output, format='PNG')
    response = HttpResponse(output.getvalue(), content_type='image/png')
    response['Cache-Control'] = 'no-store, no-cache, max-age=0'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def resolve_scan(asisten, matkul_pk, modul_pk, token, *, lock=False):
    if not asisten or asisten.role != ASISTEN_LAB_ROLE:
        return None, JsonResponse({'error': 'Hanya Asisten Lab yang dapat memindai QR.'}, status=403)

    from .views import get_praktikum_matkul_queryset

    matkul = get_praktikum_matkul_queryset(asisten).filter(pk=matkul_pk).first()
    if not matkul:
        return None, JsonResponse({'error': 'Anda tidak ditugaskan pada kelas ini.'}, status=403)
    modul = get_object_or_404(ModulPraktikum, pk=modul_pk, matkul=matkul)
    token = token.strip() if isinstance(token, str) else ''
    if not token or len(token) > 2048:
        return None, JsonResponse({'error': 'QR tidak valid.'}, status=400)
    try:
        payload = signing.loads(token, salt=QR_SALT, max_age=QR_MAX_AGE_SECONDS)
    except signing.SignatureExpired:
        return None, JsonResponse({'error': 'QR sudah kedaluwarsa. Minta mahasiswa memperbaruinya.'}, status=400)
    except signing.BadSignature:
        return None, JsonResponse({'error': 'QR tidak valid.'}, status=400)
    if not isinstance(payload, dict) or not isinstance(payload.get('user'), int) or not isinstance(payload.get('nim'), str):
        return None, JsonResponse({'error': 'QR tidak valid.'}, status=400)

    mahasiswa = Pengguna.objects.filter(
        pk=payload['user'], nim_nik=payload['nim'], is_verified=True,
        role__in={MAHASISWA_ROLE, ASISTEN_LAB_ROLE},
    ).first()
    if not mahasiswa:
        return None, JsonResponse({'error': 'Akun mahasiswa tidak ditemukan.'}, status=404)
    peserta_qs = PesertaPraktikum.objects.select_related('pengguna').filter(
        matkul=matkul, nim=mahasiswa.nim_nik, aktif=True,
    )
    if lock:
        peserta_qs = peserta_qs.select_for_update()
    peserta = peserta_qs.first()
    if not peserta or (peserta.pengguna_id and peserta.pengguna_id != mahasiswa.pk):
        return None, JsonResponse({'error': 'Mahasiswa tidak terdaftar aktif di kelas ini.'}, status=403)
    if HasilPraktikumMahasiswa.objects.filter(peserta=peserta, modul=modul).exists():
        return None, JsonResponse({'error': 'Absensi modul ini sudah tercatat.'}, status=409)
    return (asisten, mahasiswa, peserta, modul, matkul), None


@never_cache
@require_POST
def qr_scan_preview(request, matkul_pk, modul_pk):
    resolved, error = resolve_scan(getattr(request, 'current_pengguna', None), matkul_pk, modul_pk, request.POST.get('token'))
    if error:
        return error
    _, mahasiswa, peserta, modul, matkul = resolved
    return JsonResponse({
        'nama': mahasiswa.nama_pengguna,
        'nama_peserta': peserta.nama,
        'nim': mahasiswa.nim_nik,
        'foto': mahasiswa.foto.url if mahasiswa.foto else '',
        'matkul': str(matkul),
        'modul': f'Modul {modul.nomor} - {modul.judul}',
    })


@never_cache
@require_POST
def qr_scan_confirm(request, matkul_pk, modul_pk):
    with transaction.atomic():
        resolved, error = resolve_scan(getattr(request, 'current_pengguna', None), matkul_pk, modul_pk, request.POST.get('token'), lock=True)
        if error:
            return error
        asisten, mahasiswa, peserta, modul, matkul = resolved
        if not peserta.pengguna_id:
            peserta.pengguna = mahasiswa
            peserta.save(update_fields=['pengguna', 'diperbarui_pada'])
        hasil = HasilPraktikumMahasiswa(
            peserta=peserta, modul=modul, tanggal_praktikum=timezone.localdate(),
            status_absensi='hadir', sumber_absensi='qr', dicatat_oleh=asisten,
        )
        hasil.full_clean()
        hasil.save()
        transaction.on_commit(lambda: send_data_refresh(
            ('asisten_lab', 'laboran', 'mahasiswa'), 'practicum.attendance.updated',
            [reverse('asleb:praktikum_nilai', args=[matkul.pk, modul.pk]), '/'],
            related_object_id=matkul.pk, title='Absensi mahasiswa diperbarui',
        ))
    return JsonResponse({'ok': True, 'nama': mahasiswa.nama_pengguna, 'nim': mahasiswa.nim_nik})
