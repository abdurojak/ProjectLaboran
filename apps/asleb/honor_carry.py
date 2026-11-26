from decimal import Decimal, ROUND_DOWN

from .models import HonorAsleb, ItemBatchHonor


def allocate_hours(sources, budget=None, gross=None):
    if budget is None:
        budget = sum((s['hours'] for s in sources), Decimal(0))
    result = []
    for source in sources:
        hours = min(source['hours'], budget)
        if gross is not None:
            hours = min(hours, gross / source['rate'])
        if hours <= 0:
            continue
        amount = hours * source['rate']
        result.append({'source_id': source['source_id'], 'hours': str(hours), 'gross': str(amount)})
        budget -= hours
        if gross is not None:
            gross -= amount
        if budget <= 0 or (gross is not None and gross < Decimal('.005')):
            break
    return result


def carry_balance(honor):
    from .views import get_total_honor_attendance_count
    sources = list(HonorAsleb.objects.filter(asleb=honor.asleb, bulan__lte=honor.bulan).order_by('bulan', 'pk'))
    hours = {h.pk: Decimal(get_total_honor_attendance_count(h.asleb, h.bulan) * 7) for h in sources}
    target_reserved = Decimal(0)
    for h in sources:
        if h.status == 'dibayar':
            used = Decimal(h.honor_sebelum_potongan) / h.honor_per_jam
            hours[h.pk] = max(hours[h.pk] - used, Decimal(0))
            if h.pk == honor.pk:
                target_reserved += used
    items = ItemBatchHonor.objects.filter(honor__asleb=honor.asleb, batch__bulan__lte=honor.bulan).select_related('honor').order_by('batch__bulan', 'pk')
    for item in items:
        detail = item.rincian_jam
        if not detail:
            raise ValueError('Batch lama belum memiliki rincian jam. Jalankan backfill terlebih dahulu.')
        for part in detail:
            source_id = int(part['source_id'])
            used = Decimal(part['hours'])
            if source_id in hours:
                hours[source_id] = max(hours[source_id] - used, Decimal(0))
            if item.honor_id == honor.pk:
                target_reserved += used
    available = [{'source_id': h.pk, 'hours': hours[h.pk], 'rate': Decimal(h.honor_per_jam), 'month': h.bulan} for h in sources if hours[h.pk] > 0]
    plan = allocate_hours(available, sum((s['hours'] for s in available), Decimal(0)))
    gross = sum((Decimal(p['gross']) for p in plan), Decimal(0)).quantize(Decimal('.01'), rounding=ROUND_DOWN)
    fee = honor.biaya_admin if honor.status != 'dibayar' and not honor.batch_items.exists() else Decimal(0)
    carried = sum((s['hours'] for s in available if s['month'] < honor.bulan), Decimal(0))
    total_hours = sum((s['hours'] for s in available), Decimal(0))
    scheduled = sum((Decimal(p['hours']) for p in plan), Decimal(0))
    return {'sources': available, 'plan': plan, 'remaining': max(gross - fee, Decimal(0)),
            'fee': fee, 'carried_hours': carried, 'scheduled_hours': scheduled,
            'deferred_hours': max(total_hours - scheduled, Decimal(0)), 'reserved_hours': target_reserved}


def ensure_month(month):
    from django.db import transaction
    from .models import Asleb
    prior = HonorAsleb.objects.filter(bulan__lt=month).order_by('asleb_id', '-bulan')
    seen = set()
    for previous in prior:
        if previous.asleb_id in seen:
            continue
        seen.add(previous.asleb_id)
        with transaction.atomic():
            Asleb.objects.select_for_update().get(pk=previous.asleb_id)
            HonorAsleb.objects.get_or_create(asleb_id=previous.asleb_id, bulan=month, defaults={
                'total_pertemuan': 0, 'assigned_laboran_id': previous.assigned_laboran_id,
                'status': 'diproses',
            })
