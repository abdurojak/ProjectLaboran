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


def extract_grade_from_transcript(file_obj):
    if not file_obj:
        return None

    filename = getattr(file_obj, 'name', '') or ''
    text = extract_transcript_text(file_obj)
    return find_grade(f'{filename}\n{text}')


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

    try:
        file_obj.seek(0)
        reader = PdfReader(file_obj)
        return '\n'.join(page.extract_text() or '' for page in reader.pages)
    except Exception:
        return ''


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
