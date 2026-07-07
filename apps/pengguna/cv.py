from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_cv_pdf(pengguna):
    def safe(value):
        return escape(str(value or ''))

    def date_label(item):
        mulai = item.tanggal_mulai.strftime('%b %Y')
        selesai = 'Sekarang' if item.masih_berjalan else (item.tanggal_selesai.strftime('%b %Y') if item.tanggal_selesai else '-')
        return f'{mulai} - {selesai}'

    def split_lines(value):
        text = str(value or '').replace('\r\n', '\n')
        lines = []
        for raw_line in text.split('\n'):
            for piece in raw_line.split(chr(8226)):
                piece = piece.strip(' -\t')
                if piece:
                    lines.append(piece)
        return lines

    def add_section(title):
        story.extend([
            Spacer(1, 7),
            Paragraph(title, section),
            HRFlowable(width='100%', thickness=0.7, color=colors.HexColor('#111827'), spaceBefore=1, spaceAfter=5),
        ])

    def add_entry(item):
        organisation = safe(item.organisasi)
        location = safe(item.lokasi)
        left_title = organisation if not location else f'{organisation} - {location}'
        header = Table(
            [[Paragraph(f'<b>{left_title}</b>', body), Paragraph(date_label(item), date_style)]],
            colWidths=[122 * mm, 38 * mm],
            style=TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]),
        )
        story.append(header)
        subtitle_bits = [safe(item.jabatan)]
        if item.bidang_studi:
            subtitle_bits.append(safe(item.bidang_studi))
        story.append(Paragraph('<b>{}</b>'.format(' - '.join(subtitle_bits)), body))
        if item.teknologi:
            story.append(Paragraph(f'Tools: {safe(item.teknologi)}', small))
        if item.tautan:
            story.append(Paragraph(f'Link: {safe(item.tautan)}', small))
        if item.nomor_kredensial:
            story.append(Paragraph(f'Credential: {safe(item.nomor_kredensial)}', small))
        for line in split_lines(item.deskripsi):
            story.append(Paragraph(f'- {safe(line)}', bullet))
        story.append(Spacer(1, 5))

    buffer = BytesIO()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        'CvTitle',
        parent=styles['Title'],
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#111827'),
        spaceAfter=3,
    )
    contact = ParagraphStyle('CvContact', parent=styles['BodyText'], alignment=TA_CENTER, fontSize=8.5, leading=11, textColor=colors.HexColor('#1f2937'))
    body = ParagraphStyle('CvBody', parent=styles['BodyText'], alignment=TA_LEFT, fontSize=9, leading=11.5, textColor=colors.HexColor('#111827'))
    small = ParagraphStyle('CvSmall', parent=body, fontSize=8.3, leading=10.5, textColor=colors.HexColor('#374151'))
    bullet = ParagraphStyle('CvBullet', parent=body, leftIndent=4 * mm, firstLineIndent=-2 * mm, spaceBefore=1)
    date_style = ParagraphStyle('CvDate', parent=small, alignment=TA_RIGHT)
    section = ParagraphStyle('CvSection', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=13, textColor=colors.HexColor('#111827'), spaceBefore=0, spaceAfter=0)
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=14 * mm, bottomMargin=14 * mm)

    contact_parts = [
        safe(pengguna.no_hp),
        safe(pengguna.email),
        safe(pengguna.alamat),
        safe(pengguna.prodi),
    ]
    story = [
        Paragraph(safe(pengguna.nama_pengguna).upper(), title),
        Paragraph(' | '.join(part for part in contact_parts if part), contact),
        Spacer(1, 8),
    ]
    if pengguna.ringkasan_profesional:
        story.extend([Paragraph(safe(pengguna.ringkasan_profesional), body), Spacer(1, 4)])

    experiences = pengguna.pengalaman.all()
    section_map = [
        ('pengalaman', 'Work Experiences'),
        ('pendidikan', 'Education Level'),
        ('organisasi', 'Organisational Experience'),
        ('proyek', 'Projects'),
        ('sertifikasi', 'Skills, Achievements & Other Experience'),
    ]
    has_history = False
    for category, label in section_map:
        category_items = experiences.filter(kategori=category)
        if not category_items:
            continue
        has_history = True
        add_section(label)
        for item in category_items:
            add_entry(item)

    if pengguna.keahlian:
        add_section('Skills')
        story.append(Paragraph(safe(pengguna.keahlian), body))

    if not has_history and not pengguna.keahlian:
        add_section('Profile History')
        story.append(Paragraph('Belum ada riwayat yang dicantumkan.', body))

    doc.build(story)
    return buffer.getvalue()


def has_complete_asleb_profile(pengguna):
    required_values = [
        pengguna.nama_pengguna,
        pengguna.nim_nik,
        pengguna.email,
        pengguna.no_hp,
        pengguna.alamat,
        pengguna.fakultas,
        pengguna.prodi,
        pengguna.foto,
    ]
    return all(required_values) and pengguna.pengalaman.exists()
