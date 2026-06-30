from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_cv_pdf(pengguna):
    def safe(value):
        return escape(str(value or '-'))

    buffer = BytesIO()
    styles = getSampleStyleSheet()
    title = ParagraphStyle('CvTitle', parent=styles['Title'], alignment=TA_CENTER, textColor=colors.HexColor('#0f5f66'))
    section = ParagraphStyle('CvSection', parent=styles['Heading2'], textColor=colors.HexColor('#0f5f66'), spaceBefore=10)
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    story = [
        Paragraph(safe(pengguna.nama_pengguna), title),
        Paragraph(f'{safe(pengguna.email)} | {safe(pengguna.no_hp)} | {safe(pengguna.prodi)}, {safe(pengguna.fakultas)}', styles['BodyText']),
        Spacer(1, 10),
        Paragraph('Profil', section),
        Table([
            ['NIM/NIK', safe(pengguna.nim_nik)],
            ['Program Studi', safe(pengguna.prodi)],
            ['Fakultas', safe(pengguna.fakultas)],
            ['Alamat', safe(pengguna.alamat)],
        ], colWidths=[35 * mm, 120 * mm], style=TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ])),
    ]
    if pengguna.ringkasan_profesional:
        story.extend([
            Paragraph('Tentang', section),
            Paragraph(safe(pengguna.ringkasan_profesional), styles['BodyText']),
        ])
    if pengguna.keahlian:
        story.extend([
            Paragraph('Keahlian', section),
            Paragraph(safe(pengguna.keahlian), styles['BodyText']),
        ])
    experiences = pengguna.pengalaman.all()
    if not experiences:
        story.extend([Paragraph('Riwayat Profil', section), Paragraph('Belum ada riwayat yang dicantumkan.', styles['BodyText'])])
    for category, label in pengguna.pengalaman.model.KATEGORI_CHOICES:
        category_items = experiences.filter(kategori=category)
        if category_items:
            story.append(Paragraph(label, section))
        for item in category_items:
            end_label = 'Sekarang' if item.masih_berjalan else (item.tanggal_selesai.strftime('%b %Y') if item.tanggal_selesai else '-')
            details = ' | '.join(filter(None, [item.bidang_studi, item.lokasi]))
            story.extend([
                Paragraph(f'<b>{safe(item.jabatan)}</b> - {safe(item.organisasi)}', styles['BodyText']),
                Paragraph(f'{item.tanggal_mulai.strftime("%b %Y")} - {end_label}', styles['Italic']),
            ])
            if details:
                story.append(Paragraph(safe(details), styles['BodyText']))
            story.extend([Paragraph(safe(item.deskripsi), styles['BodyText']), Spacer(1, 8)])
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
