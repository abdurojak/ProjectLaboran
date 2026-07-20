from pathlib import Path

from django.conf import settings
from PIL import Image, UnidentifiedImageError
from mutagen.mp4 import MP4, MP4StreamInfoError
from rest_framework import serializers

from apps.asleb.models import AbsensiMasukAsleb
from apps.jadwal.models import JadwalPraktikum
from apps.inventaris.models import Lokasi


def absolute_file_url(request, field):
    if not field:
        return None
    return request.build_absolute_uri(field.url)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LaboranInventoryCreateSerializer(serializers.Serializer):
    nama = serializers.CharField(max_length=150)
    jumlah = serializers.IntegerField(min_value=1, max_value=1000)
    lokasi_id = serializers.PrimaryKeyRelatedField(
        source='lokasi', queryset=Lokasi.objects.all()
    )
    keterangan = serializers.CharField(required=False, allow_blank=True, max_length=3000)
    foto = serializers.ImageField(required=False, allow_null=True)

    def validate_foto(self, photo):
        return validate_inventory_photo(photo)


def validate_inventory_photo(photo):
    extension = Path(photo.name).suffix.lower()
    content_type = (getattr(photo, 'content_type', '') or '').lower()
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
    if extension not in allowed_extensions or content_type not in allowed_types:
        raise serializers.ValidationError('Foto barang harus berformat JPG, PNG, atau WebP.')
    if photo.size > 5 * 1024 * 1024:
        raise serializers.ValidationError('Ukuran setiap foto barang maksimal 5 MB.')
    try:
        Image.open(photo).verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise serializers.ValidationError('Isi file foto barang tidak valid.') from exc
    finally:
        photo.seek(0)
    return photo


class ProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nama = serializers.CharField(source='nama_pengguna')
    identitas = serializers.CharField(source='nim_nik')
    email = serializers.EmailField()
    role = serializers.CharField()
    program_studi = serializers.CharField(source='prodi')
    foto_url = serializers.SerializerMethodField()

    def get_foto_url(self, obj):
        return absolute_file_url(self.context['request'], obj.foto)


class ScheduleSerializer(serializers.ModelSerializer):
    hari_display = serializers.CharField(source='get_hari_display', read_only=True)
    laboratorium = serializers.SerializerMethodField()
    status_absensi = serializers.SerializerMethodField()
    waktu_absensi = serializers.SerializerMethodField()

    class Meta:
        model = JadwalPraktikum
        fields = [
            'id', 'mata_kuliah', 'kelas', 'hari', 'hari_display', 'waktu_mulai',
            'waktu_selesai', 'laboratorium', 'status_absensi', 'waktu_absensi',
        ]

    def get_laboratorium(self, obj):
        return obj.get_display_ruangan_nama()

    def get_status_absensi(self, obj):
        override = self.context.get('status_by_schedule', {}).get(obj.pk)
        if override:
            return override
        attendance = self.context.get('attendance_by_schedule', {}).get(obj.pk)
        return attendance.status if attendance else 'belum_absen'

    def get_waktu_absensi(self, obj):
        attendance = self.context.get('attendance_by_schedule', {}).get(obj.pk)
        return attendance.waktu_masuk if attendance else None


class AttendanceSerializer(serializers.ModelSerializer):
    mata_kuliah = serializers.SerializerMethodField()
    kelas = serializers.SerializerMethodField()
    laboratorium = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    foto_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = AbsensiMasukAsleb
        fields = [
            'id', 'tanggal_absensi', 'waktu_masuk', 'mata_kuliah', 'kelas',
            'laboratorium', 'status', 'status_display', 'latitude', 'longitude',
            'jarak_lokasi_meter', 'akurasi_gps_meter', 'foto_url', 'video_url',
        ]

    def get_laboratorium(self, obj):
        return obj.jadwal.get_display_ruangan_nama() if obj.jadwal_id else 'Jadwal sudah dihapus'

    def get_mata_kuliah(self, obj):
        return obj.jadwal.mata_kuliah if obj.jadwal_id else 'Jadwal sudah dihapus'

    def get_kelas(self, obj):
        return obj.jadwal.kelas if obj.jadwal_id else '-'

    def get_foto_url(self, obj):
        return absolute_file_url(self.context['request'], obj.foto_absensi)

    def get_video_url(self, obj):
        return absolute_file_url(self.context['request'], obj.video_absensi)


class CheckInSerializer(serializers.Serializer):
    jadwal_id = serializers.IntegerField(min_value=1)
    foto_absensi = serializers.ImageField()
    video_absensi = serializers.FileField(required=False, allow_null=True)

    def validate_foto_absensi(self, photo):
        extension = Path(photo.name).suffix.lower()
        content_type = (getattr(photo, 'content_type', '') or '').lower()
        if extension not in {'.jpg', '.jpeg', '.png'} or content_type not in {'image/jpeg', 'image/png'}:
            raise serializers.ValidationError('Foto harus berformat JPG, JPEG, atau PNG.')
        if photo.size > settings.ABSENSI_MAX_PHOTO_SIZE_MB * 1024 * 1024:
            raise serializers.ValidationError(f'Ukuran foto maksimal {settings.ABSENSI_MAX_PHOTO_SIZE_MB} MB.')
        try:
            Image.open(photo).verify()
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise serializers.ValidationError('Isi file foto tidak valid.') from exc
        finally:
            photo.seek(0)
        return photo

    def validate_video_absensi(self, video):
        if not video:
            return video
        extension = Path(video.name).suffix.lower()
        content_type = (getattr(video, 'content_type', '') or '').lower()
        if extension != '.mp4' or content_type != 'video/mp4':
            raise serializers.ValidationError('Video harus berformat MP4.')
        if video.size > settings.ABSENSI_MAX_VIDEO_SIZE_MB * 1024 * 1024:
            raise serializers.ValidationError(f'Ukuran video maksimal {settings.ABSENSI_MAX_VIDEO_SIZE_MB} MB.')
        try:
            duration = MP4(video.file).info.length
        except (MP4StreamInfoError, OSError, ValueError, AttributeError) as exc:
            raise serializers.ValidationError('Isi file video MP4 tidak valid.') from exc
        finally:
            video.seek(0)
        if duration > settings.ABSENSI_MAX_VIDEO_DURATION_SECONDS + 0.5:
            raise serializers.ValidationError(
                f'Durasi video maksimal {settings.ABSENSI_MAX_VIDEO_DURATION_SECONDS} detik.'
            )
        return video
