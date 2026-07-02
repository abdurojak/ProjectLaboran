import re
from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse


def get_public_registration_url():
    base_url = settings.PUBLIC_ACCESS_BASE_URL.rstrip('/') + '/'
    return urljoin(base_url, reverse('pendaftaran_asleb:pendaftaran_public').lstrip('/'))


GRADE_PATTERN = re.compile(
    r'(?:nilai|grade|huruf|mutu)\s*[:=\-]?\s*((?:A|B|C|D|E)(?:[+-])?)\b|\b((?:A|B|C|D|E)(?:[+-])?)\s*(?:nilai|grade|huruf|mutu)\b',
    re.IGNORECASE,
)
TRANSCRIPT_GRADE_PATTERN = re.compile(r'\b((?:A|B|C|D|E)(?:[+-])?)\b', re.IGNORECASE)

PASSING_GRADES = {'A', 'B'}


def extract_grade_from_transcript(file_obj, matkul=None):
    if not file_obj:
        return None

    filename = getattr(file_obj, 'name', '') or ''
    text = extract_transcript_text(file_obj)
    transcript_text = f'{filename}\n{text}'
    return find_grade_for_course(transcript_text, matkul) or find_grade(transcript_text)


def analyze_transcript(file_obj, matkul=None, expected_nim=''):
    """Extract the selected course grade and verify the account NIM."""
    if not file_obj:
        return None, False

    filename = getattr(file_obj, 'name', '') or ''
    text = extract_transcript_text(file_obj)
    transcript_text = f'{filename}\n{text}'
    grade = find_grade_for_course(transcript_text, matkul) or find_grade(transcript_text)
    return grade, transcript_contains_nim(text, expected_nim)


def transcript_contains_nim(text, expected_nim):
    expected_nim = re.sub(r'\D', '', str(expected_nim or ''))
    if not text or not expected_nim:
        return False

    # OCR sometimes inserts spaces or hyphens between otherwise adjacent digits.
    separated_digits = r'[\s\-]*'.join(re.escape(digit) for digit in expected_nim)
    return bool(re.search(rf'(?<!\d){separated_digits}(?!\d)', text))


def extract_transcript_text(file_obj):
    filename = (getattr(file_obj, 'name', '') or '').lower()

    try:
        current_position = file_obj.tell()
    except (AttributeError, OSError):
        current_position = None

    try:
        if filename.endswith(('.txt', '.csv')):
            return read_uploaded_text(file_obj)

        if filename.endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff')):
            return ocr_image(file_obj)

        if filename.endswith('.pdf'):
            return normalize_transcript_text(extract_pdf_text(file_obj) or ocr_pdf(file_obj))
    finally:
        if current_position is not None:
            try:
                file_obj.seek(current_position)
            except (AttributeError, OSError):
                pass

    return ''


def read_uploaded_text(file_obj):
    try:
        content = file_obj.read()
    except (AttributeError, OSError):
        return ''

    if isinstance(content, str):
        return content

    for encoding in ['utf-8', 'latin-1']:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue

    return ''


def extract_pdf_text(file_obj):
    pdf_bytes = get_pdf_bytes(file_obj)
    if not pdf_bytes:
        return ''

    if should_prefer_pdfium(pdf_bytes):
        text = extract_pdf_text_with_pdfium_bytes(pdf_bytes)
        if text:
            return text

    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None

    if PdfReader is not None:
        for pdf_stream in get_pdf_stream_candidates_from_bytes(pdf_bytes):
            try:
                reader = PdfReader(pdf_stream, strict=False)
                text = '\n'.join(page.extract_text() or '' for page in reader.pages)
                if normalize_transcript_text(text):
                    return text
            except Exception:
                continue

    return extract_pdf_text_with_pdfium_bytes(pdf_bytes)


def extract_pdf_text_with_pdfium(file_obj):
    return extract_pdf_text_with_pdfium_bytes(get_pdf_bytes(file_obj))


def extract_pdf_text_with_pdfium_bytes(pdf_bytes):
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return ''

    for pdf_stream in get_pdf_stream_candidates_from_bytes(pdf_bytes):
        try:
            pdf_stream.seek(0)
            document = pdfium.PdfDocument(pdf_stream.read())
            page_text = []
            for page in document:
                text_page = page.get_textpage()
                page_text.append(text_page.get_text_range() or '')
                text_page.close()
                page.close()
            text = '\n'.join(page_text)
            document.close()
            if normalize_transcript_text(text):
                return text
        except Exception:
            continue

    return ''


def get_pdf_bytes(file_obj):
    try:
        file_obj.seek(0)
        return file_obj.read()
    except (AttributeError, OSError):
        return b''


def should_prefer_pdfium(pdf_bytes):
    pdf_start = pdf_bytes.find(b'%PDF')
    eof_marker = pdf_bytes.rfind(b'%%EOF')
    return pdf_start > 0 or eof_marker == -1


def get_pdf_stream_candidates(file_obj):
    return get_pdf_stream_candidates_from_bytes(get_pdf_bytes(file_obj))


def get_pdf_stream_candidates_from_bytes(data):
    from io import BytesIO

    if not data:
        return []

    candidates = [BytesIO(data)]
    pdf_start = data.find(b'%PDF')
    if pdf_start > 0:
        candidates.append(BytesIO(data[pdf_start:]))

    return candidates


def ocr_image(file_obj):
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return ''

    try:
        file_obj.seek(0)
        image = Image.open(file_obj)
        return pytesseract.image_to_string(image, lang='ind+eng')
    except Exception:
        return ''


def ocr_pdf(file_obj):
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError:
        return ''

    try:
        file_obj.seek(0)
        pages = convert_from_bytes(file_obj.read(), first_page=1, last_page=3)
        return '\n'.join(pytesseract.image_to_string(page, lang='ind+eng') for page in pages)
    except Exception:
        return ''


def find_grade(text):
    if not text:
        return None

    match = GRADE_PATTERN.search(text)
    if not match:
        return None

    return next(normalize_grade_value(value) for value in match.groups() if value)


def is_passing_grade(grade):
    return (grade or '').upper() in PASSING_GRADES


def find_grade_for_course(text, matkul):
    if not text or not matkul:
        return None

    course_codes = get_course_code_candidates(matkul)
    course_names = get_course_name_candidates(matkul)
    normalized_lines = [normalize_spaces(line) for line in text.splitlines() if normalize_spaces(line)]

    if course_codes:
        for line_number, line in enumerate(normalized_lines):
            if not line_matches_course_code(line, course_codes):
                continue

            grade = find_grade(line) or find_last_grade(line)
            if not grade:
                window = ' '.join(normalized_lines[line_number:line_number + 3])
                grade = find_grade(window) or find_last_grade(window)

            if grade:
                return grade

    for line_number, line in enumerate(normalized_lines):
        normalized_line = line.lower()
        if not any(course_name in normalized_line for course_name in course_names):
            continue

        grade = find_grade(line) or find_last_grade(line)
        if not grade:
            window = ' '.join(normalized_lines[line_number:line_number + 3])
            grade = find_grade(window) or find_last_grade(window)

        if grade:
            return grade

    return None


def get_course_code_candidates(matkul):
    raw_candidates = [
        getattr(matkul, 'kode_mk', ''),
    ]
    return [
        normalize_spaces(candidate).upper()
        for candidate in raw_candidates
        if normalize_spaces(candidate)
    ]


def line_matches_course_code(line, course_codes):
    normalized_line = normalize_spaces(line).upper()
    return any(
        re.search(rf'(?<![A-Z0-9]){re.escape(course_code)}(?![A-Z0-9])', normalized_line)
        for course_code in course_codes
    )


def get_course_name_candidates(matkul):
    raw_candidates = [
        getattr(matkul, 'nama', ''),
        str(matkul).split(' - ')[0],
    ]
    return [
        normalize_spaces(candidate).lower()
        for candidate in raw_candidates
        if normalize_spaces(candidate)
    ]


def normalize_spaces(value):
    return re.sub(r'\s+', ' ', str(value)).strip()


def normalize_transcript_text(text):
    if not text:
        return ''

    cleaned = str(text).replace('\ufeff', ' ').replace('\ufffe', ' ').replace('\x00', ' ')
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def normalize_grade_value(value):
    cleaned = normalize_spaces(value).upper()
    return cleaned[:1] if cleaned else None


def find_last_grade(text):
    matches = TRANSCRIPT_GRADE_PATTERN.findall(text or '')
    if not matches:
        return None

    return normalize_grade_value(matches[-1])
