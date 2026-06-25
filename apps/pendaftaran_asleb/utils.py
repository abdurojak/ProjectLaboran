from urllib.parse import urljoin
import re

from django.conf import settings
from django.urls import reverse


def get_public_registration_url():
    base_url = settings.PUBLIC_ACCESS_BASE_URL.rstrip('/') + '/'
    return urljoin(base_url, reverse('pendaftaran_asleb:pendaftaran_public').lstrip('/'))


GRADE_PATTERN = re.compile(
    r'(?:nilai|grade|huruf|mutu)\s*[:=\-]?\s*(A|B|C)\b|\b(A|B|C)\s*(?:nilai|grade|huruf|mutu)\b',
    re.IGNORECASE,
)
TRANSCRIPT_GRADE_PATTERN = re.compile(r'\b(A|B|C)\b', re.IGNORECASE)


def extract_grade_from_transcript(file_obj, matkul=None):
    if not file_obj:
        return None

    filename = getattr(file_obj, 'name', '') or ''
    text = extract_transcript_text(file_obj)
    transcript_text = f'{filename}\n{text}'
    return find_grade_for_course(transcript_text, matkul) or find_grade(transcript_text)


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
            return extract_pdf_text(file_obj) or ocr_pdf(file_obj)
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
    try:
        from pypdf import PdfReader
    except ImportError:
        return ''

    for pdf_stream in get_pdf_stream_candidates(file_obj):
        try:
            reader = PdfReader(pdf_stream, strict=False)
            return '\n'.join(page.extract_text() or '' for page in reader.pages)
        except Exception:
            continue

    return ''


def get_pdf_stream_candidates(file_obj):
    from io import BytesIO

    try:
        file_obj.seek(0)
        data = file_obj.read()
    except (AttributeError, OSError):
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

    return next(value.upper() for value in match.groups() if value)


def find_grade_for_course(text, matkul):
    if not text or not matkul:
        return None

    course_names = get_course_name_candidates(matkul)
    normalized_lines = [normalize_spaces(line) for line in text.splitlines() if normalize_spaces(line)]

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


def find_last_grade(text):
    matches = TRANSCRIPT_GRADE_PATTERN.findall(text or '')
    if not matches:
        return None

    return matches[-1].upper()
