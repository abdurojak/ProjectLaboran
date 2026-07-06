from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.asleb.models import AbsensiMasukAsleb, PengaturanAbsensiAsleb
from apps.pendaftaran_asleb.services import sync_expired_asleb_periods
from apps.pengguna.models import Pengguna

from .jwt_service import create_token_pair, decode_token
from .serializers import (
    AttendanceSerializer,
    CheckInSerializer,
    LoginSerializer,
    ProfileSerializer,
    RefreshSerializer,
    ScheduleSerializer,
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
        asleb = get_active_asleb(pengguna)
        if pengguna.role != 'asisten_lab' or not asleb:
            return api_error(
                'Akun tidak memiliki akses sebagai Asisten Lab aktif.',
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
        pengguna = Pengguna.objects.filter(pk=payload['sub'], is_verified=True, role='asisten_lab').first()
        if not pengguna or not get_active_asleb(pengguna):
            return api_error('Akses Asisten Lab sudah tidak aktif.', 'role_not_allowed', status.HTTP_403_FORBIDDEN)
        return Response({'tokens': create_token_pair(pengguna)})


class LogoutView(APIView):
    def post(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileView(APIView):
    def get(self, request):
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
    def get(self, request):
        asleb = get_active_asleb(request.user)
        today = timezone.localdate()
        schedules = list(get_owned_schedules(asleb))
        today_key = WEEKDAY_KEYS[today.weekday()]
        today_schedules = [item for item in schedules if item.hari == today_key]
        context = attendance_context(asleb, today_schedules, today)
        context['request'] = request
        return Response({
            'profile': ProfileSerializer(request.user, context={'request': request}).data,
            'mata_kuliah': get_asleb_course_labels(asleb),
            'tanggal': today,
            'jadwal_hari_ini': ScheduleSerializer(today_schedules, many=True, context=context).data,
            'status_absensi_hari_ini': (
                'tidak_ada_jadwal'
                if not today_schedules
                else 'sudah_absen'
                if all(item.pk in context['attendance_by_schedule'] for item in today_schedules)
                else 'belum_absen'
            ),
        })


class ScheduleListView(APIView):
    def get(self, request):
        asleb = get_active_asleb(request.user)
        schedules = list(get_owned_schedules(asleb))
        context = attendance_context(asleb, schedules)
        context['request'] = request
        return Response({'results': ScheduleSerializer(schedules, many=True, context=context).data})


class ScheduleDetailView(APIView):
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
        except IntegrityError:
            return api_error('Anda sudah melakukan absensi masuk untuk jadwal ini.', 'duplicate_attendance')
        return Response(
            AttendanceSerializer(attendance, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class AttendanceHistoryView(APIView):
    def get(self, request):
        asleb = get_active_asleb(request.user)
        queryset = AbsensiMasukAsleb.objects.filter(asleb=asleb).select_related(
            'jadwal', 'jadwal__ruangan', 'jadwal__ruangan_tambahan'
        )
        return Response({
            'results': AttendanceSerializer(queryset, many=True, context={'request': request}).data,
        })


class LocationConfigView(APIView):
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
