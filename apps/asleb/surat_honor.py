from collections import OrderedDict
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.db.models import Q
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


MONTH_NAMES = [
    '',
    'Januari',
    'Februari',
    'Maret',
    'April',
    'Mei',
    'Juni',
    'Juli',
    'Agustus',
    'September',
    'Oktober',
    'November',
    'Desember',
]


LAB_SIGNATURES = OrderedDict([
    ('Laboratorium Pemrograman', 'Anung B. Ariwibowo, S.Kom., M.Kom.'),
    ('Laboratorium Rekayasa Data', 'Is Mardianto, S.Si., M.Kom.'),
    ('Laboratorium Sains Data dan Analitik', 'Dian Pratiwi, S.T., MTI'),
    ('Laboratorium Sistem dan Keamanan Informasi', 'Ir. Gatot Budi Santoso, M.Kom.'),
    ('Laboratorium Sistem Informasi dan Rekayasa Perangkat Lunak', 'Drs. Syaifudin, M.Si., Ph.D.'),
])

LAB_NAMES_BY_ROOM_CODE = {
    'LAB-RPL': 'Laboratorium Sistem Informasi dan Rekayasa Perangkat Lunak',
    'LAB-SDA': 'Laboratorium Sains Data dan Analitik',
    'LAB-RD': 'Laboratorium Rekayasa Data',
    'LAB-PRG': 'Laboratorium Pemrograman',
    'LAB-SKI': 'Laboratorium Sistem dan Keamanan Informasi',
}


@dataclass(frozen=True)
class HonorLabRow:
    honor: object
    matkul_labels: tuple[str, ...]


LAB_KEYWORDS = [
    ('Laboratorium Sistem Informasi dan Rekayasa Perangkat Lunak', [
        'enterprise resource planning',
        'erp',
        'pemrograman web',
        'pemrograman mobile',
        'rekayasa perangkat lunak',
        'sistem informasi',
    ]),
    ('Laboratorium Sains Data dan Analitik', [
        'analitik data',
        'machine learning',
        'probabilitas',
        'statistika',
        'sains data',
    ]),
    ('Laboratorium Rekayasa Data', [
        'manajemen data',
        'data warehouse',
        'rekayasa data',
        'basis data',
    ]),
    ('Laboratorium Pemrograman', [
        'pemrograman berorientasi objek',
        'struktur data',
        'algoritma',
        'pemrograman',
    ]),
    ('Laboratorium Sistem dan Keamanan Informasi', [
        'jaringan komputer',
        'keamanan',
        'sistem keamanan',
    ]),
]


def month_year_label(date_value):
    return f'{MONTH_NAMES[date_value.month]} {date_value.year}'


def date_label(date_value):
    return f'{date_value.day} {MONTH_NAMES[date_value.month]} {date_value.year}'


def classify_laboratorium(matkul):
    laboratorium = getattr(matkul, 'laboratorium', None)
    if laboratorium:
        canonical_name = LAB_NAMES_BY_ROOM_CODE.get(laboratorium.kode)
        if canonical_name:
            return canonical_name
    normalized = str(matkul or '').lower()
    for lab_name, keywords in LAB_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return lab_name
    return 'Laboratorium Pemrograman'


def get_honor_courses(honor, bulan):
    from apps.pendaftaran_asleb.models import AslabAssignment, MataKuliahAsleb, RiwayatAsleb

    month_start = bulan.replace(day=1)
    next_month = (
        month_start.replace(year=month_start.year + 1, month=1)
        if month_start.month == 12
        else month_start.replace(month=month_start.month + 1)
    )
    month_end = next_month - timedelta(days=1)
    courses = list(
        MataKuliahAsleb.objects.filter(
            aslab_slots__assignments__asleb=honor.asleb,
            aslab_slots__assignments__mulai_pada__lte=month_end,
        )
        .filter(
            Q(aslab_slots__assignments__berakhir_pada__isnull=True)
            | Q(aslab_slots__assignments__berakhir_pada__gte=month_start)
        )
        .filter(aslab_slots__assignments__status__in=[
            AslabAssignment.STATUS_ACTIVE,
            AslabAssignment.STATUS_RESIGNED,
            AslabAssignment.STATUS_TERMINATED,
            AslabAssignment.STATUS_REPLACED,
            AslabAssignment.STATUS_COMPLETED,
        ])
        .select_related('laboratorium')
        .distinct()
        .order_by('nama', 'kelas', 'pk')
    )
    if courses:
        return courses

    history_course_ids = RiwayatAsleb.objects.filter(
        nim=honor.asleb.nim,
        periode__mulai__lte=month_end,
        periode__selesai__gte=month_start,
        matkul__isnull=False,
    ).values_list('matkul_id', flat=True)
    courses = list(
        MataKuliahAsleb.objects.filter(pk__in=history_course_ids)
        .select_related('laboratorium')
        .order_by('nama', 'kelas', 'pk')
    )
    if courses:
        return courses

    legacy_label = (honor.asleb.matkul or '').strip()
    if not legacy_label:
        return []
    return list(
        MataKuliahAsleb.objects.filter(
            Q(nama__iexact=legacy_label) | Q(kode__iexact=legacy_label)
        ).select_related('laboratorium').order_by('nama', 'kelas', 'pk')
    )


def group_honors_by_laboratorium(honors, bulan):
    grouped = OrderedDict((lab_name, []) for lab_name in LAB_SIGNATURES)
    for honor in honors:
        courses = get_honor_courses(honor, bulan)
        if not courses:
            legacy_label = honor.asleb.matkul or '-'
            lab_name = classify_laboratorium(legacy_label)
            grouped.setdefault(lab_name, []).append(HonorLabRow(honor, (legacy_label,)))
            continue

        labels_by_lab = OrderedDict()
        for course in courses:
            lab_name = classify_laboratorium(course)
            labels = labels_by_lab.setdefault(lab_name, [])
            if course.nama not in labels:
                labels.append(course.nama)
        for lab_name, labels in labels_by_lab.items():
            grouped.setdefault(lab_name, []).append(HonorLabRow(honor, tuple(labels)))
    return OrderedDict((lab_name, items) for lab_name, items in grouped.items() if items)


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='Letter',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        name='LetterLeft',
        parent=styles['Letter'],
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name='LetterRight',
        parent=styles['Letter'],
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name='TitleCenter',
        parent=styles['Normal'],
        fontName='Times-Bold',
        fontSize=12,
        leading=15,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name='TableCell',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=8,
        leading=10,
    ))
    styles.add(ParagraphStyle(
        name='TableHeader',
        parent=styles['TableCell'],
        fontName='Times-Bold',
        alignment=TA_CENTER,
    ))
    return styles


def paragraph(text, style):
    return Paragraph(str(text).replace('\n', '<br/>'), style)


def generate_surat_honor_pdf(honors, nomor_surat, tanggal_surat, bulan, perihal):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2.0 * cm,
        leftMargin=2.0 * cm,
        topMargin=3.9 * cm,
        bottomMargin=1.8 * cm,
    )
    styles = build_styles()
    story = []
    honors = list(honors)
    grouped = group_honors_by_laboratorium(honors, bulan)
    bulan_label = month_year_label(bulan)

    story.extend(build_cover_letter(styles, grouped, nomor_surat, tanggal_surat, bulan_label, perihal))
    for lab_name, lab_honors in grouped.items():
        story.append(PageBreak())
        story.extend(build_lampiran_page(
            styles,
            lab_name,
            lab_honors,
            bulan_label,
        ))

    if not grouped:
        story.append(PageBreak())
        story.append(paragraph('Tidak ada data honor asisten laboratorium untuk bulan ini.', styles['LetterLeft']))

    doc.build(story, onFirstPage=draw_kop_surat, onLaterPages=draw_kop_surat)
    buffer.seek(0)
    return buffer.getvalue()


def draw_kop_surat(canvas, doc):
    kop_path = settings.BASE_DIR / 'apps' / 'core' / 'static' / 'core' / 'img' / 'kop-surat-trisakti.png'
    page_width, page_height = A4
    if kop_path.exists():
        image_width = 17.2 * cm
        image_height = 2.45 * cm
        canvas.drawImage(
            str(kop_path),
            (page_width - image_width) / 2,
            page_height - 3.15 * cm,
            width=image_width,
            height=image_height,
            preserveAspectRatio=True,
            mask='auto',
        )


def build_cover_letter(styles, grouped, nomor_surat, tanggal_surat, bulan_label, perihal):
    lab_names = list(grouped.keys()) or list(LAB_SIGNATURES.keys())
    story = [
        build_letter_meta_table(styles, nomor_surat, max(len(lab_names), 1), tanggal_surat, perihal),
        Spacer(1, 0.95 * cm),
        paragraph('Kepada Yth.<br/><b>Dekan</b><br/>Fakultas Teknologi Industri<br/>Universitas Trisakti<br/>Jakarta', styles['LetterLeft']),
        Spacer(1, 0.8 * cm),
        paragraph('Dengan hormat,', styles['LetterLeft']),
        Spacer(1, 0.25 * cm),
        paragraph(
            'bersama ini kami sampaikan laporan kegiatan Asisten Laboratorium yang ada di Jurusan Teknik Informatika '
            'Fakultas Teknologi Industri Universitas Trisakti:',
            styles['Letter'],
        ),
    ]
    for index, lab_name in enumerate(lab_names, start=1):
        story.append(paragraph(f'{index}. {lab_name}', styles['LetterLeft']))
    story.extend([
        paragraph(
            f'pada bulan <b>{bulan_label}</b> dengan perincian pada lampiran surat ini, mohon dapat diproses lebih lanjut.',
            styles['Letter'],
        ),
        paragraph(
            'Demikian kami sampaikan, atas perhatian serta bantuan yang diberikan kami ucapkan terima kasih.',
            styles['Letter'],
        ),
        Spacer(1, 0.8 * cm),
        build_chair_signature(styles),
        Spacer(1, 0.35 * cm),
        paragraph('<b>Tembusan:</b><br/>1. <b>Kepala Tata Usaha FTI</b><br/>2. <b>Kasubag SDM FTI</b>', styles['LetterLeft']),
    ])
    return story


def build_letter_meta_table(styles, nomor_surat, lampiran_count, tanggal_surat, perihal):
    left = Table([
        [paragraph('Nomor', styles['LetterLeft']), paragraph(':', styles['LetterLeft']), paragraph(nomor_surat, styles['LetterLeft'])],
        [paragraph('Lampiran', styles['LetterLeft']), paragraph(':', styles['LetterLeft']), paragraph(f'{lampiran_count} (Lembar)', styles['LetterLeft'])],
        [paragraph('Perihal', styles['LetterLeft']), paragraph(':', styles['LetterLeft']), paragraph(perihal.replace(' Jurusan', '<br/>Jurusan'), styles['LetterLeft'])],
    ], colWidths=[2.3 * cm, 0.25 * cm, 8.9 * cm])
    left.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    meta = Table([
        [left, paragraph(f'Jakarta, {date_label(tanggal_surat)}', styles['LetterLeft'])],
    ], colWidths=[11.5 * cm, 5.5 * cm])
    meta.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return meta


def build_chair_signature(styles):
    signature = Table([
        [paragraph('Jurusan Teknik Informatika<br/>Ketua,', styles['TitleCenter'])],
        [''],
        [paragraph('Syandra Sari, M.Kom.', styles['TitleCenter'])],
    ], colWidths=[6.5 * cm], rowHeights=[1.0 * cm, 1.8 * cm, 0.5 * cm])
    signature.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    wrapper = Table([['', signature]], colWidths=[9.7 * cm, 6.5 * cm])
    wrapper.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return wrapper


def build_lab_signature(styles, lab_name):
    signature = Table([
        [paragraph(f'{lab_name}<br/>Jurusan Teknik Informatika<br/>Kepala Laboratorium', styles['LetterRight'])],
        [''],
        [paragraph(LAB_SIGNATURES.get(lab_name, 'Kepala Laboratorium'), styles['LetterRight'])],
    ], colWidths=[7.4 * cm], rowHeights=[1.0 * cm, 1.5 * cm, 0.5 * cm])
    signature.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    wrapper = Table([['', signature]], colWidths=[10.2 * cm, 7.4 * cm])
    wrapper.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return wrapper


def build_lampiran_page(styles, lab_name, honors, bulan_label, combined=False):
    story = [
        paragraph('LAPORAN KEGIATAN ASISTEN', styles['TitleCenter']),
        paragraph(lab_name.upper(), styles['TitleCenter']),
        paragraph('JURUSAN TEKNIK INFORMATIKA FTI - USAKTI', styles['TitleCenter']),
        paragraph(f'BULAN {bulan_label.upper()}', styles['TitleCenter']),
        Spacer(1, 0.45 * cm),
    ]

    data = [[
        paragraph('No.', styles['TableHeader']),
        paragraph('NAMA MAHASISWA', styles['TableHeader']),
        paragraph('NIM', styles['TableHeader']),
        paragraph('MATA KULIAH', styles['TableHeader']),
        paragraph('STATUS', styles['TableHeader']),
        paragraph('JUMLAH JAM', styles['TableHeader']),
    ]]
    for index, item in enumerate(honors, start=1):
        honor = item.honor if isinstance(item, HonorLabRow) else item
        matkul_labels = (
            item.matkul_labels
            if isinstance(item, HonorLabRow)
            else (honor.asleb.matkul or '-',)
        )
        data.append([
            str(index),
            paragraph(honor.asleb.nama, styles['TableCell']),
            paragraph(honor.asleb.nim, styles['TableCell']),
            paragraph('<br/>'.join(matkul_labels), styles['TableCell']),
            paragraph(honor.get_level_display(), styles['TableCell']),
            str(honor.total_akhir),
        ])

    table = Table(data, colWidths=[1.0 * cm, 5.4 * cm, 2.8 * cm, 4.2 * cm, 2.2 * cm, 2.0 * cm])
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (4, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.extend([
        table,
        Spacer(1, 0.75 * cm),
        build_chair_signature(styles) if combined else build_lab_signature(styles, lab_name),
    ])
    return story
