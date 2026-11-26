from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Asleb, BatchHonor, HonorAsleb, ItemBatchHonor


def balances(honor):
    from .honor_carry import carry_balance
    from .views import get_total_honor_attendance_count
    count = get_total_honor_attendance_count(honor.asleb, honor.bulan)
    entitlement = Decimal(min(count * 7, 60) * honor.honor_per_jam)
    entitlement = max(entitlement - honor.biaya_admin, Decimal(0))
    legacy_paid = honor.jumlah if honor.status == 'dibayar' else Decimal(0)
    allocated = honor.batch_items.aggregate(total=Sum('nominal'))['total'] or Decimal(0)
    paid = honor.batch_items.filter(dibayar_pada__isnull=False).aggregate(total=Sum('nominal'))['total'] or Decimal(0)
    carry = carry_balance(honor)
    return {'entitlement': entitlement, 'paid': legacy_paid + paid,
            'allocated': allocated, **carry,
            'overpaid': max(legacy_paid + paid - entitlement, Decimal(0))}


def staff(request):
    user = getattr(request, 'current_pengguna', None)
    if not user or user.role not in {'admin', 'laboran'}:
        raise PermissionDenied
    return user


def batch_list(request):
    user = staff(request)
    month = parse_date(request.GET.get('bulan', timezone.localdate().strftime('%Y-%m')) + '-01')
    month = month or timezone.localdate().replace(day=1)
    if month == timezone.localdate().replace(day=1):
        from .honor_carry import ensure_month
        ensure_month(month)
    honors = HonorAsleb.objects.filter(bulan=month).select_related('asleb', 'assigned_laboran')
    batches = BatchHonor.objects.filter(bulan=month).select_related('laboran').prefetch_related('items__honor__asleb')
    if user.role == 'laboran':
        honors = honors.filter(assigned_laboran=user)
        batches = batches.filter(laboran=user)
    rows = [{'honor': h, **balances(h)} for h in honors]
    for row in rows:
        row['can_allocate'] = (
            user.role == 'laboran' and month >= timezone.localdate().replace(day=1)
            and row['remaining'] > 0 and row['allocated'] == 0
        )
    return render(request, 'asleb/batch_honor.html', {
        'rows': rows, 'batches': batches, 'month': month.strftime('%Y-%m'),
        'can_pay': user.role == 'laboran',
        'can_create': any(row['can_allocate'] for row in rows),
    })


@require_POST
@transaction.atomic
def create_batch(request):
    user = staff(request)
    if user.role != 'laboran':
        raise PermissionDenied
    month = parse_date(request.POST.get('bulan', '') + '-01')
    if month and month < timezone.localdate().replace(day=1):
        messages.error(request, 'Alokasi bulan lama tetap dikunci. Modul tersisa dibukukan pada bulan berjalan.')
        return redirect('asleb:honor_batches')
    if not month or request.POST.get('konfirmasi') != 'KUNCI BATCH':
        messages.error(request, 'Isi bulan dan ketik KUNCI BATCH untuk mengunci alokasi dana.')
        return redirect('asleb:honor_batches')
    honors = list(HonorAsleb.objects.filter(bulan=month, assigned_laboran=user).order_by('asleb_id'))
    # The same Aslab mutex is used by attendance synchronization and legacy payment.
    list(Asleb.objects.select_for_update().filter(pk__in=[h.asleb_id for h in honors]).order_by('pk'))
    honors = list(HonorAsleb.objects.select_for_update().filter(pk__in=[h.pk for h in honors]))
    items = []
    try:
        funds = Decimal(request.POST.get('dana_diterima', '0'))
        admin = Decimal(request.POST.get('cadangan_admin', '0') or '0')
        if not admin.is_finite() or admin < 0 or admin != admin.quantize(Decimal('.01')):
            raise ValueError
        if not funds.is_finite() or funds <= 0 or funds != funds.quantize(Decimal('.01')):
            raise ValueError
        from apps.pendaftaran_asleb.replacement_services import payment_eligible_honors
        for h in honors:
            amount = Decimal(request.POST.get(f'nominal_{h.pk}', '0') or '0')
            if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('.01')):
                raise ValueError
            if amount:
                if h.batch_items.exists():
                    raise ValueError
                if amount > balances(h)['remaining'] or not payment_eligible_honors(HonorAsleb.objects.filter(pk=h.pk)).exists():
                    raise ValueError
                from .honor_carry import allocate_hours
                balance = balances(h)
                details = allocate_hours(balance['sources'], max(Decimal(60) - balance['reserved_hours'], Decimal(0)), amount + balance['fee'])
                items.append((h, amount, details))
        if not items or sum(amount for _, amount, _ in items) + admin != funds:
            raise ValueError
    except (ValueError, InvalidOperation):
        messages.error(request, 'Alokasi harus sama dengan dana diterima, tidak melebihi sisa kewajiban, dan honor tidak sedang ditahan.')
        return redirect('asleb:honor_batches')
    batch = BatchHonor.objects.create(bulan=month, laboran=user, dana_diterima=funds, cadangan_admin=admin, catatan=request.POST.get('catatan', '').strip())
    ItemBatchHonor.objects.bulk_create([ItemBatchHonor(batch=batch, honor=h, nominal=amount, rincian_jam=details) for h, amount, details in items])
    messages.success(request, f'Batch #{batch.pk} dikunci. Nominal alokasi tidak berubah mengikuti koreksi absensi.')
    return redirect('asleb:honor_batches')


@require_POST
@transaction.atomic
def pay_item(request, pk):
    user = staff(request)
    item = get_object_or_404(ItemBatchHonor.objects.select_related('batch', 'honor'), pk=pk)
    if user.role != 'laboran' or item.batch.laboran_id != user.pk:
        raise PermissionDenied
    return_url = f"{reverse('asleb:honor_batches')}?bulan={item.batch.bulan:%Y-%m}#transfer-{item.pk}"
    Asleb.objects.select_for_update().get(pk=item.honor.asleb_id)
    item = ItemBatchHonor.objects.select_for_update().get(pk=pk)
    from apps.pendaftaran_asleb.replacement_services import payment_eligible_honors
    if not payment_eligible_honors(HonorAsleb.objects.filter(pk=item.honor_id)).exists():
        messages.error(request, 'Honor sedang ditahan. Selesaikan proses penggantian aslab dahulu.')
        return redirect(return_url)
    if item.dibayar_pada:
        messages.error(request, 'Transfer ini sudah tercatat.')
        return redirect(return_url)
    proof = request.FILES.get('bukti_transfer')
    transfer_date = parse_date(request.POST.get('tanggal_transfer', ''))
    if not proof or proof.size > 5 * 1024 * 1024 or not transfer_date or transfer_date > timezone.localdate():
        messages.error(request, 'Isi tanggal transfer yang valid dan bukti pembayaran maksimal 5 MB.')
        return redirect(return_url)
    from .forms import KonfirmasiTransferHonorForm
    validation = KonfirmasiTransferHonorForm({'tanggal_transfer': transfer_date}, {'bukti_transfer': proof}, instance=item.honor)
    if not validation.is_valid():
        messages.error(request, 'Bukti transfer tidak valid. Gunakan format bukti pembayaran yang didukung.')
        return redirect(return_url)
    item.tanggal_transfer = transfer_date
    item.bukti_transfer = proof
    item.dibayar_pada = timezone.now()
    item.save(update_fields=['tanggal_transfer', 'bukti_transfer', 'dibayar_pada'])
    messages.success(request, 'Transfer batch berhasil dicatat.')
    return redirect(return_url)
