from copy import copy

from .models import HonorAsleb, ItemBatchHonor


def honor_estimate(nim, month):
    from decimal import Decimal
    from .honor_carry import carry_balance
    honor = HonorAsleb.objects.filter(asleb__nim=nim, bulan=month).first()
    if not honor:
        previous = HonorAsleb.objects.filter(asleb__nim=nim, bulan__lt=month).order_by('-bulan').first()
        if previous:
            honor, _ = HonorAsleb.objects.get_or_create(asleb=previous.asleb, bulan=month, defaults={'assigned_laboran_id': previous.assigned_laboran_id})
    if not honor:
        return {'current': Decimal(0), 'carried': Decimal(0), 'due': Decimal(0)}
    balance = carry_balance(honor)
    carried = sum((Decimal(p['gross']) for p in balance['plan'] if int(p['source_id']) != honor.pk), Decimal(0))
    pending = Decimal(0)
    for item in honor.batch_items.filter(dibayar_pada__isnull=True):
        pending += item.nominal
        old_gross = sum((Decimal(p['gross']) for p in item.rincian_jam if int(p['source_id']) != honor.pk), Decimal(0))
        carried += min(old_gross, item.nominal)
    return {'current': max(balance['remaining'] + pending - carried, Decimal(0)),
            'carried': carried, 'due': balance['remaining'] + pending}


def paid_honor_rows(nim):
    rows = list(HonorAsleb.objects.filter(asleb__nim=nim, status='dibayar').select_related('asleb'))
    for item in ItemBatchHonor.objects.filter(honor__asleb__nim=nim, dibayar_pada__isnull=False).select_related('honor__asleb'):
        row = copy(item.honor)
        row.jumlah = item.nominal
        row.status = 'dibayar'
        row.tanggal_transfer = item.tanggal_transfer
        row.bukti_transfer = item.bukti_transfer
        row.biaya_admin = 0
        rows.append(row)
    return sorted(rows, key=lambda row: (row.bulan, row.tanggal_transfer or row.bulan), reverse=True)
