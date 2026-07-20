from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.asleb.models import AbsensiMasukAsleb, PengaturanAbsensiAsleb
from apps.asleb.views import sync_honor_from_mobile_absensi
from apps.asleb.models import HonorAsleb
from apps.core.views import bot_answer
from apps.inventaris.models import (
    ACTIVE_PEMINJAMAN_STATUSES,
    Barang,
    FotoInventarisBarang,
    InventarisBarang,
    Lokasi,
)
from apps.kalender.realtime import send_peminjaman_status_update
from apps.peminjaman.models import PeminjamanAlat
from apps.peminjaman.notifications import send_peminjaman_status_notification
from apps.peminjaman.services import update_peminjaman_status
from apps.pendaftaran_asleb.services import sync_expired_asleb_periods
from apps.pengguna.models import Pengguna

from .authentication import has_mobile_access
from .jwt_service import create_token_pair, decode_token
from .permissions import IsAsistenLab, IsLaboran
from .serializers import (
    AttendanceSerializer,
    CheckInSerializer,
    LaboranInventoryCreateSerializer,
    LoginSerializer,
    ProfileSerializer,
    RefreshSerializer,
    ScheduleSerializer,
    absolute_file_url,
    validate_inventory_photo,
)
from .services import (
    WEEKDAY_KEYS,
    get_active_asleb,
    get_asleb_course_labels,
    get_checkin_window,
    get_owned_schedules,
    validate_schedule_time,
)


def api_error(message, code, http_status=status.HTTP_400_BAD_REQUEST, **extra):
    return Response({'detail': message, 'code': code, **extra}, status=http_status)


def attendance_context(asleb, schedules, date_value=None):
    date_value = date_value or timezone.localdate()
    attendance = AbsensiMasukAsleb.objects.filter(
        asleb=asleb,
        jadwal__in=schedules,
        tanggal_absensi=date_value,
    )
    attendance_by_schedule = {item.jadwal_id: item for item in attendance}
    status_by_schedule = {}
    local_now = timezone.localtime()
    today_key = WEEKDAY_KEYS[date_value.weekday()]
    for schedule in schedules:
        if schedule.pk in attendance_by_schedule:
            continue
        if schedule.hari == today_key:
            _, _, ends_at = get_checkin_window(schedule, date_value)
            if local_now > ends_at:
                status_by_schedule[schedule.pk] = 'tidak_hadir'
    return {
        'attendance_by_schedule': attendance_by_schedule,
        'status_by_schedule': status_by_schedule,
    }


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['identifier'].strip()
        pengguna = Pengguna.objects.filter(
            Q(nim_nik=identifier) | Q(email__iexact=identifier)
        ).first()
        if not pengguna or not check_password(serializer.validated_data['password'], pengguna.password):
            return api_error('Identitas atau password salah.', 'invalid_credentials', status.HTTP_401_UNAUTHORIZED)
        if not pengguna.is_verified:
            return api_error('Akun belum diverifikasi.', 'account_unverified', status.HTTP_403_FORBIDDEN)
        sync_expired_asleb_periods()
        pengguna.refresh_from_db(fields=['role'])
        if not has_mobile_access(pengguna):
            return api_error(
                'Aplikasi hanya dapat diakses oleh Asisten Lab aktif atau Laboran.',
                'role_not_allowed',
                status.HTTP_403_FORBIDDEN,
            )
        return Response({
            'tokens': create_token_pair(pengguna),
            'user': ProfileSerializer(pengguna, context={'request': request}).data,
        })


class RefreshTokenView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = decode_token(serializer.validated_data['refresh'], 'refresh')
        pengguna = Pengguna.objects.filter(pk=payload['sub'], is_verified=True).first()
        if not pengguna or not has_mobile_access(pengguna):
            return api_error('Akses aplikasi mobile sudah tidak aktif.', 'role_not_allowed', status.HTTP_403_FORBIDDEN)
        return Response({'tokens': create_token_pair(pengguna)})


class LogoutView(APIView):
    def post(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileView(APIView):
    def get(self, request):
        if request.user.role == 'laboran':
            return Response({
                'user': ProfileSerializer(request.user, context={'request': request}).data,
                'asleb': None,
            })
        asleb = get_active_asleb(request.user)
        return Response({
            'user': ProfileSerializer(request.user, context={'request': request}).data,
            'asleb': {
                'id': asleb.pk,
                'status': asleb.status,
                'level': asleb.level_otomatis,
                'mata_kuliah': get_asleb_course_labels(asleb),
                'periode': asleb.periode_aktif.nama if asleb.periode_aktif else None,
            },
        })


class DashboardView(APIView):
    permission_classes = [IsAsistenLab]

    def get(self, request):
        asleb = get_active_asleb(request.user)
        today = timezone.localdate()
        schedules = list(get_owned_schedules(asleb))
        today_key = WEEKDAY_KEYS[today.weekday()]
        today_schedules = [item for item in schedules if item.hari == today_key]
        context = attendance_context(asleb, today_schedules, today)
        context['request'] = request
        honor_queryset = HonorAsleb.objects.filter(asleb=asleb).order_by('-bulan')
        honor_bulan_ini = honor_queryset.filter(
            bulan__year=today.year,
            bulan__month=today.month,
        ).first()
        total_pending = honor_queryset.exclude(status='dibayar').aggregate(total=Sum('jumlah'))['total'] or 0
        return Response({
            'profile': ProfileSerializer(request.user, context={'request': request}).data,
            'mata_kuliah': get_asleb_course_labels(asleb),
            'tanggal': today,
            'jadwal_hari_ini': ScheduleSerializer(today_schedules, many=True, context=context).data,
            'honor': {
                'bulan_ini': {
                    'bulan': honor_bulan_ini.bulan if honor_bulan_ini else None,
                    'jumlah': honor_bulan_ini.jumlah if honor_bulan_ini else 0,
                    'status': honor_bulan_ini.status if honor_bulan_ini else 'belum_ada',
                    'total_pertemuan': honor_bulan_ini.total_pertemuan if honor_bulan_ini else 0,
                    'biaya_admin': honor_bulan_ini.biaya_admin if honor_bulan_ini else 0,
                    'total_sebelum_potongan': honor_bulan_ini.honor_sebelum_potongan if honor_bulan_ini else 0,
                },
                'total_pending': total_pending,
                'riwayat': [
                    {
                        'bulan': honor.bulan,
                        'jumlah': honor.jumlah,
                        'status': honor.status,
                        'total_pertemuan': honor.total_pertemuan,
                    }
                    for honor in honor_queryset[:6]
                ],
            },
            'status_absensi_hari_ini': (
                'tidak_ada_jadwal'
                if not today_schedules
                else 'sudah_absen'
                if all(item.pk in context['attendance_by_schedule'] for item in today_schedules)
                else 'belum_absen'
            ),
        })


class ChatbotView(APIView):
    def post(self, request):
        message = str(request.data.get('message') or '').strip()[:1000]
        if not message:
            return api_error('Tulis pertanyaan terlebih dahulu.', 'empty_message')
        return Response({'answer': bot_answer(message, request.user)})


class ScheduleListView(APIView):
    permission_classes = [IsAsistenLab]

    def get(self, request):
        asleb = get_active_asleb(request.user)
        schedules = list(get_owned_schedules(asleb))
        context = attendance_context(asleb, schedules)
        context['request'] = request
        return Response({'results': ScheduleSerializer(schedules, many=True, context=context).data})


class ScheduleDetailView(APIView):
    permission_classes = [IsAsistenLab]

    def get(self, request, pk):
        asleb = get_active_asleb(request.user)
        schedule = get_owned_schedules(asleb).filter(pk=pk).first()
        if not schedule:
            return api_error('Jadwal tidak ditemukan atau bukan milik Anda.', 'schedule_not_owned', status.HTTP_404_NOT_FOUND)
        context = attendance_context(asleb, [schedule])
        context['request'] = request
        valid, reason, _ = validate_schedule_time(schedule)
        already_checked_in = schedule.pk in context['attendance_by_schedule']
        return Response({
            'schedule': ScheduleSerializer(schedule, context=context).data,
            'can_check_in': valid and not already_checked_in and PengaturanAbsensiAsleb.get_solo().dibuka,
            'check_in_message': (
                'Anda sudah melakukan absensi masuk untuk jadwal ini.'
                if already_checked_in else reason or 'Absensi masuk tersedia.'
            ),
        })


class CheckInView(APIView):
    permission_classes = [IsAsistenLab]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asleb = get_active_asleb(request.user)
        if not PengaturanAbsensiAsleb.get_solo().dibuka:
            return api_error('Absensi Asisten Lab sedang ditutup oleh pengelola.', 'attendance_closed')

        schedule = get_owned_schedules(asleb).select_for_update().filter(
            pk=serializer.validated_data['jadwal_id']
        ).first()
        if not schedule:
            return api_error('Jadwal bukan milik Asisten Lab yang sedang login.', 'schedule_not_owned', status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        if AbsensiMasukAsleb.objects.filter(asleb=asleb, jadwal=schedule, tanggal_absensi=today).exists():
            return api_error('Anda sudah melakukan absensi masuk untuk jadwal ini.', 'duplicate_attendance')

        valid_time, reason, attendance_status = validate_schedule_time(schedule)
        if not valid_time:
            return api_error(reason, 'invalid_schedule_time')

        try:
            attendance = AbsensiMasukAsleb.objects.create(
                asleb=asleb,
                jadwal=schedule,
                tanggal_absensi=today,
                waktu_masuk=timezone.now(),
                status=attendance_status,
                foto_absensi=serializer.validated_data['foto_absensi'],
                video_absensi=serializer.validated_data.get('video_absensi') or '',
            )
            sync_honor_from_mobile_absensi(attendance)
        except IntegrityError:
            return api_error('Anda sudah melakukan absensi masuk untuk jadwal ini.', 'duplicate_attendance')
        return Response(
            AttendanceSerializer(attendance, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class AttendanceHistoryView(APIView):
    permission_classes = [IsAsistenLab]

    def get(self, request):
        asleb = get_active_asleb(request.user)
        queryset = AbsensiMasukAsleb.objects.filter(asleb=asleb).select_related(
            'jadwal', 'jadwal__ruangan', 'jadwal__ruangan_tambahan'
        )
        return Response({
            'results': AttendanceSerializer(queryset, many=True, context={'request': request}).data,
        })


class LocationConfigView(APIView):
    permission_classes = [IsAsistenLab]

    def get(self, request):
        return Response({
            'attendance_open': PengaturanAbsensiAsleb.get_solo().dibuka,
            'center_latitude': settings.ABSENSI_CENTER_LATITUDE,
            'center_longitude': settings.ABSENSI_CENTER_LONGITUDE,
            'radius_meters': settings.ABSENSI_RADIUS_METERS,
            'max_gps_accuracy_meters': settings.ABSENSI_MAX_GPS_ACCURACY_METERS,
            'early_checkin_minutes': settings.ABSENSI_EARLY_CHECKIN_MINUTES,
            'max_photo_size_mb': settings.ABSENSI_MAX_PHOTO_SIZE_MB,
            'max_video_size_mb': settings.ABSENSI_MAX_VIDEO_SIZE_MB,
            'max_video_duration_seconds': settings.ABSENSI_MAX_VIDEO_DURATION_SECONDS,
        })


def inventory_payload(request, inventory):
    gallery = [absolute_file_url(request, item.foto) for item in inventory.galeri_foto.all()]
    cover = absolute_file_url(request, inventory.foto)
    photos = ([cover] if cover else []) + gallery
    borrowed = getattr(inventory, 'jumlah_dipinjam_aktif', 0) or 0
    return {
        'id': inventory.pk,
        'kode': inventory.kode_inventaris,
        'nama': inventory.nama,
        'jumlah': inventory.jumlah,
        'dipinjam': borrowed,
        'tersedia': max(inventory.jumlah - borrowed, 0),
        'keterangan': inventory.keterangan,
        'foto_url': cover or (gallery[0] if gallery else None),
        'foto_urls': list(dict.fromkeys(item for item in photos if item)),
    }


class LaboranDashboardView(APIView):
    permission_classes = [IsLaboran]

    def get(self, request):
        inventory = InventarisBarang.objects.aggregate(total=Sum('jumlah'))['total'] or 0
        borrowed = PeminjamanAlat.objects.filter(status__in=ACTIVE_PEMINJAMAN_STATUSES).count()
        pending = PeminjamanAlat.objects.filter(status='diajukan').count()
        recent = PeminjamanAlat.objects.select_related('barang').order_by('-dibuat_pada')[:5]
        return Response({
            'profile': ProfileSerializer(request.user, context={'request': request}).data,
            'summary': {
                'total_barang': inventory,
                'menunggu_persetujuan': pending,
                'sedang_dipinjam': borrowed,
                'lokasi': Lokasi.objects.count(),
            },
            'peminjaman_terbaru': [loan_payload(item) for item in recent],
        })


class LaboranLocationListView(APIView):
    permission_classes = [IsLaboran]

    def get(self, request):
        return Response({'results': [
            {'id': item.pk, 'kode': item.kode_lokasi, 'nama': item.nama_lokasi}
            for item in Lokasi.objects.order_by('nama_lokasi')
        ]})


class LaboranInventoryListCreateView(APIView):
    permission_classes = [IsLaboran]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        query = str(request.query_params.get('q') or '').strip()
        queryset = InventarisBarang.objects.annotate(
            jumlah_dipinjam_aktif=Count(
                'detail_barang__peminjaman',
                filter=Q(detail_barang__peminjaman__status__in=ACTIVE_PEMINJAMAN_STATUSES),
            )
        ).prefetch_related('galeri_foto')
        if query:
            queryset = queryset.filter(Q(nama__icontains=query) | Q(kode_inventaris__icontains=query))
        return Response({'results': [inventory_payload(request, item) for item in queryset]})

    @transaction.atomic
    def post(self, request):
        serializer = LaboranInventoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gallery_files = request.FILES.getlist('foto_galeri')
        if len(gallery_files) > 8:
            return api_error('Foto tambahan maksimal 8 file.', 'too_many_photos')
        try:
            gallery_files = [validate_inventory_photo(item) for item in gallery_files]
        except ValidationError as exc:
            return Response({'foto_galeri': exc.detail}, status=status.HTTP_400_BAD_REQUEST)

        values = serializer.validated_data
        inventory = InventarisBarang.objects.create(
            nama=values['nama'],
            jumlah=values['jumlah'],
            foto=values.get('foto'),
            keterangan=values.get('keterangan', ''),
        )
        for _ in range(inventory.jumlah):
            Barang.objects.create(
                inventaris=inventory,
                nama=inventory.nama,
                jumlah=inventory.jumlah,
                lokasi=values['lokasi'],
                kondisi='baik',
            )
        for order, photo in enumerate(gallery_files, start=1):
            FotoInventarisBarang.objects.create(inventaris=inventory, foto=photo, urutan=order)
        inventory.jumlah_dipinjam_aktif = 0
        return Response(inventory_payload(request, inventory), status=status.HTTP_201_CREATED)


def loan_payload(loan):
    return {
        'id': loan.pk,
        'kode': loan.kode_pinjam,
        'barang': loan.barang.nama,
        'kode_barang': loan.barang.kode_barang,
        'peminjam': loan.nama_peminjam,
        'nim': loan.nim,
        'tanggal_pinjam': loan.tanggal_pinjam,
        'tanggal_kembali': loan.tanggal_kembali,
        'status': loan.status,
        'status_display': loan.get_status_display(),
        'catatan': loan.catatan,
    }


class LaboranLoanListView(APIView):
    permission_classes = [IsLaboran]

    def get(self, request):
        requested_status = str(request.query_params.get('status') or '').strip()
        queryset = PeminjamanAlat.objects.select_related('barang').order_by('-dibuat_pada')
        if requested_status:
            queryset = queryset.filter(status=requested_status)
        return Response({'results': [loan_payload(item) for item in queryset[:200]]})


class LaboranLoanStatusView(APIView):
    permission_classes = [IsLaboran]
    allowed_transitions = {
        'diajukan': {'dipinjam'},
        'dipinjam': {'dikembalikan', 'hilang', 'rusak'},
        'hilang': {'digantikan'},
        'rusak': {'digantikan'},
    }

    @transaction.atomic
    def post(self, request, pk):
        loan = PeminjamanAlat.objects.select_for_update().select_related('barang').filter(pk=pk).first()
        if not loan:
            return api_error('Peminjaman tidak ditemukan.', 'loan_not_found', status.HTTP_404_NOT_FOUND)
        next_status = str(request.data.get('status') or '').strip()
        if next_status not in self.allowed_transitions.get(loan.status, set()):
            return api_error('Perubahan status peminjaman tidak diizinkan.', 'invalid_status_transition')
        update_peminjaman_status(loan, next_status)
        send_peminjaman_status_notification(loan)
        transaction.on_commit(
            lambda loan_id=loan.pk: send_peminjaman_status_update(
                PeminjamanAlat.objects.select_related('barang').get(pk=loan_id)
            )
        )
        return Response(loan_payload(loan))
