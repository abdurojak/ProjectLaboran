from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone
from django.db.models import Sum

from apps.inventaris.models import Barang
from apps.kalender.models import KegiatanKalender

from .models import PenyesuaianSkorKredit, PeminjamanTransaksi


LIBUR_NASIONAL_TETAP = {
    (1, 1),
    (5, 1),
    (6, 1),
    (8, 17),
    (12, 25),
}


@dataclass(frozen=True)
class CreditProfile:
    score: int
    label: str
    has_late_history: bool
    has_active_overdue: bool
    late_transactions: int
    problem_transactions: int
    on_time_returns: int
    recovery_points: int
    manual_adjustment: int

    @property
    def can_submit(self):
        return self.score >= 40

    @property
    def blocked_for_low_score(self):
        return self.score < 40


def is_non_operational_date(value):
    if value.weekday() == 6 or (value.month, value.day) in LIBUR_NASIONAL_TETAP:
        return True
    return KegiatanKalender.objects.filter(tanggal=value, hari_libur=True).exists()


def adjust_return_date(value):
    adjusted = value
    while is_non_operational_date(adjusted):
        adjusted += timedelta(days=1)
    return adjusted


def get_credit_profile(nim, today=None):
    today = today or timezone.localdate()
    score = 100
    late_transactions = 0
    problem_transactions = 0
    has_active_overdue = False
    on_time_returns = 0
    recovery_points = 0
    transactions = list(
        PeminjamanTransaksi.objects.filter(nim=nim).prefetch_related('detail')
    )
    transactions.sort(key=lambda item: (
        item.tanggal_dikembalikan or today,
        item.tanggal_pinjam,
        item.pk,
    ))

    for transaksi in transactions:
        statuses = {detail.status for detail in transaksi.detail.all()}
        risk = transaksi.risiko
        if risk in {'hilang', 'rusak'} or {'hilang', 'rusak'} & statuses:
            score -= sum(detail.potongan_skor for detail in transaksi.detail.all())
            problem_transactions += 1

    score = max(0, score)
    manual_adjustment = PenyesuaianSkorKredit.objects.filter(
        pengguna__nim_nik=nim,
    ).aggregate(total=Sum('nilai_penyesuaian'))['total'] or 0
    score = min(100, max(0, score + manual_adjustment))
    has_late_history = late_transactions > 0
    label = 'Baik' if score >= 80 else ('Waspada' if score >= 60 else 'Buruk')
    return CreditProfile(
        score=score,
        label=label,
        has_late_history=has_late_history,
        has_active_overdue=has_active_overdue,
        late_transactions=late_transactions,
        problem_transactions=problem_transactions,
        on_time_returns=on_time_returns,
        recovery_points=recovery_points,
        manual_adjustment=manual_adjustment,
    )


def sync_barang_after_peminjaman_status(peminjaman, next_status):
    barang = peminjaman.barang
    if not barang:
        return

    updated_fields = []

    if next_status == 'rusak' and barang.kondisi == 'baik':
        barang.kondisi = 'rusak_ringan'
        updated_fields.append('kondisi')
    elif next_status == 'digantikan' and barang.kondisi != 'baik':
        barang.kondisi = 'baik'
        updated_fields.append('kondisi')

    if updated_fields:
        updated_fields.append('diperbarui_pada')
        barang.save(update_fields=updated_fields)


def update_peminjaman_status(peminjaman, next_status, *, potongan_skor=None, laboran=None):
    if peminjaman.status == next_status:
        return False

    if next_status in {'hilang', 'rusak'}:
        if not isinstance(potongan_skor, int) or not 1 <= potongan_skor <= 100 or laboran is None or laboran.role != 'laboran':
            raise ValueError('Laboran wajib menentukan potongan skor 1 sampai 100 poin.')

    sync_barang_after_peminjaman_status(peminjaman, next_status)
    peminjaman.status = next_status
    update_fields = ['status', 'diperbarui_pada']
    if next_status in {'hilang', 'rusak'}:
        peminjaman.potongan_skor = potongan_skor
        peminjaman.potongan_skor_oleh = laboran
        update_fields.extend(['potongan_skor', 'potongan_skor_oleh'])
    peminjaman.save(update_fields=update_fields)
    if peminjaman.transaksi_id:
        transaksi = peminjaman.transaksi
        update_fields = []
        if next_status == 'hilang' and transaksi.risiko != 'hilang':
            transaksi.risiko = 'hilang'
            update_fields.append('risiko')
        elif next_status == 'rusak' and transaksi.risiko == 'normal':
            transaksi.risiko = 'rusak'
            update_fields.append('risiko')
        group_is_finished = not transaksi.detail.exclude(
            status__in={'dikembalikan', 'digantikan', 'ditolak'},
        ).exists()
        if group_is_finished and not transaksi.tanggal_dikembalikan:
            transaksi.tanggal_dikembalikan = timezone.localdate()
            update_fields.append('tanggal_dikembalikan')
        if update_fields:
            update_fields.append('diperbarui_pada')
            transaksi.save(update_fields=update_fields)
    return True
