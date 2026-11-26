from copy import copy

from .models import HonorAsleb, ItemBatchHonor


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
