from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .models import Asleb, BatchHonor, HonorAsleb, ItemBatchHonor


def balances(honor):
    from .views import get_total_honor_attendance_count
    count = get_total_honor_attendance_count(honor.asleb, honor.bulan)
    entitlement = Decimal(min(count * 7, 60) * honor.honor_per_jam)
    entitlement = max(entitlement - honor.biaya_admin, Decimal(0))
    legacy_paid = honor.jumlah if honor.status == 'dibayar' else Decimal(0)
    allocated = honor.batch_items.aggregate(total=Sum('nominal'))['total'] or Decimal(0)
    paid = honor.batch_items.filter(dibayar_pada__isnull=False).aggregate(total=Sum('nominal'))['total'] or Decimal(0)
    return {'entitlement': entitlement, 'paid': legacy_paid + paid,
            'allocated': allocated, 'remaining': max(entitlement - legacy_paid - allocated, Decimal(0)),
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
    honors = HonorAsleb.objects.filter(bulan=month).select_related('asleb', 'assigned_laboran')
    batches = BatchHonor.objects.filter(bulan=month).select_related('laboran').prefetch_related('items__honor__asleb')
    if user.role == 'laboran':
        honors = honors.filter(assigned_laboran=user)
        batches = batches.filter(laboran=user)
    rows = [{'honor': h, **balances(h)} for h in honors]
    return render(request, 'asleb/batch_honor.html', {
        'rows': rows, 'batches': batches, 'month': month.strftime('%Y-%m'),
        'can_pay': user.role == 'laboran',
    })


@require_POST
@transaction.atomic
def create_batch(request):
    user = staff(request)
    if user.role != 'laboran':
        raise PermissionDenied
    month = parse_date(request.POST.get('bulan', '') + '-01')
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
        if not funds.is_finite() or funds <= 0 or funds != funds.quantize(Decimal('.01')):
            raise ValueError
        from apps.pendaftaran_asleb.replacement_services import payment_eligible_honors
        for h in honors:
            amount = Decimal(request.POST.get(f'nominal_{h.pk}', '0') or '0')
            if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('.01')):
                raise ValueError
            if amount:
                if amount > balances(h)['remaining'] or not payment_eligible_honors(HonorAsleb.objects.filter(pk=h.pk)).exists():
                    raise ValueError
                items.append((h, amount))
        if not items or sum(amount for _, amount in items) != funds:
            raise ValueError
    except (ValueError, InvalidOperation):
        messages.error(request, 'Alokasi harus sama dengan dana diterima, tidak melebihi sisa kewajiban, dan honor tidak sedang ditahan.')
        return redirect('asleb:honor_batches')
    batch = BatchHonor.objects.create(bulan=month, laboran=user, dana_diterima=funds, catatan=request.POST.get('catatan', '').strip())
    ItemBatchHonor.objects.bulk_create([ItemBatchHonor(batch=batch, honor=h, nominal=amount) for h, amount in items])
    messages.success(request, f'Batch #{batch.pk} dikunci. Nominal alokasi tidak berubah mengikuti koreksi absensi.')
    return redirect('asleb:honor_batches')


@require_POST
@transaction.atomic
def pay_item(request, pk):
    user = staff(request)
    item = get_object_or_404(ItemBatchHonor.objects.select_related('batch', 'honor'), pk=pk)
    if user.role != 'laboran' or item.batch.laboran_id != user.pk:
        raise PermissionDenied
    Asleb.objects.select_for_update().get(pk=item.honor.asleb_id)
    item = ItemBatchHonor.objects.select_for_update().get(pk=pk)
    from apps.pendaftaran_asleb.replacement_services import payment_eligible_honors
    if not payment_eligible_honors(HonorAsleb.objects.filter(pk=item.honor_id)).exists():
        messages.error(request, 'Honor sedang ditahan. Selesaikan proses penggantian aslab dahulu.')
        return redirect('asleb:honor_batches')
    if item.dibayar_pada:
        messages.error(request, 'Transfer ini sudah tercatat.')
        return redirect('asleb:honor_batches')
    proof = request.FILES.get('bukti_transfer')
    transfer_date = parse_date(request.POST.get('tanggal_transfer', ''))
    if not proof or proof.size > 5 * 1024 * 1024 or not transfer_date or transfer_date > timezone.localdate():
        messages.error(request, 'Isi tanggal transfer yang valid dan bukti pembayaran maksimal 5 MB.')
        return redirect('asleb:honor_batches')
    from .forms import KonfirmasiTransferHonorForm
    validation = KonfirmasiTransferHonorForm({'tanggal_transfer': transfer_date}, {'bukti_transfer': proof}, instance=item.honor)
    if not validation.is_valid():
        messages.error(request, 'Bukti transfer tidak valid. Gunakan format bukti pembayaran yang didukung.')
        return redirect('asleb:honor_batches')
    item.tanggal_transfer = transfer_date
    item.bukti_transfer = proof
    item.dibayar_pada = timezone.now()
    item.save(update_fields=['tanggal_transfer', 'bukti_transfer', 'dibayar_pada'])
    messages.success(request, 'Transfer batch berhasil dicatat.')
    return redirect('asleb:honor_batches')
