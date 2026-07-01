from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


MONTHS = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']


def build_surat_pdf(surat):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    normal = ParagraphStyle('LetterBody', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=13.5)
    justify = ParagraphStyle('LetterJustify', parent=normal, alignment=TA_JUSTIFY)
    right = ParagraphStyle('LetterRight', parent=normal, alignment=TA_RIGHT)
    small = ParagraphStyle('LetterSmall', parent=normal, fontSize=8.5, leading=11)
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, leftMargin=0.72 * inch, rightMargin=0.72 * inch, topMargin=0.48 * inch, bottomMargin=0.42 * inch)
    static_dir = Path(settings.BASE_DIR) / 'apps' / 'surat' / 'static' / 'surat' / 'img'
    story = []
    header = static_dir / 'fti-header.png'
    if header.exists():
        story.extend([Image(str(header), width=7.0 * inch, height=1.10 * inch), Spacer(1, 5)])
    tanggal = f'Jakarta, {surat.tanggal.day:02d} {MONTHS[surat.tanggal.month - 1]} {surat.tanggal.year}'
    story.extend([
        Paragraph(tanggal, right), Spacer(1, 8),
        Table([
            [Paragraph('Nomor', normal), ':', Paragraph(escape(surat.nomor), normal)],
            [Paragraph('Hal', normal), ':', Paragraph(escape(surat.hal), normal)],
            [Paragraph('Lamp', normal), ':', Paragraph(escape(surat.lampiran), normal)],
        ], colWidths=[0.72 * inch, 0.18 * inch, 5.95 * inch], style=TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)])),
        Spacer(1, 8), Paragraph('Kepada Yth.', normal), Paragraph(f'<b>{escape(surat.tujuan_jabatan)}</b>', normal),
        Paragraph(escape(surat.tujuan_instansi).replace('\n', '<br/>'), normal), Spacer(1, 10),
        Paragraph(escape(surat.isi), justify), Spacer(1, 9),
    ])
    rows = [[Paragraph('<b>No</b>', small), Paragraph('<b>Nama Barang</b>', small), Paragraph('<b>Spesifikasi</b>', small), Paragraph('<b>Jumlah</b>', small), Paragraph('<b>Keterangan</b>', small)]]
    for index, item in enumerate(surat.items, 1):
        rows.append([Paragraph(str(index), small)] + [Paragraph(escape(item.get(key, '-')), small) for key in ('nama', 'spesifikasi', 'jumlah', 'keterangan')])
    table = Table(rows, colWidths=[0.34 * inch, 1.55 * inch, 1.40 * inch, 0.88 * inch, 2.65 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.65, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'), ('ALIGN', (3, 1), (3, -1), 'CENTER'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.extend([table, Spacer(1, 9), Paragraph('Demikian surat pengajuan ini kami sampaikan. Atas perhatian dan kerja sama Bapak/Ibu, kami ucapkan terima kasih.', normal), Spacer(1, 7)])
    signature = static_dir / 'ski-signature.png'
    signature_flow = Image(str(signature), width=2.45 * inch, height=1.18 * inch) if signature.exists() else Spacer(1, 1.05 * inch)
    sign_table = Table([['', Paragraph(escape(surat.jabatan_penandatangan), normal)], ['', Paragraph(escape(surat.laboratorium), normal)], ['', signature_flow], ['', Paragraph(f'<u><b>{escape(surat.nama_penandatangan)}</b></u>', normal)]], colWidths=[3.9 * inch, 2.9 * inch])
    sign_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
    story.append(sign_table)
    doc.build(story)
    return buffer.getvalue()
