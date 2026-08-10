from django import forms
from django.conf import settings
from PIL import Image, UnidentifiedImageError


def validate_safe_image_upload(uploaded_file, *, max_bytes=None, max_pixels=None):
    """Reject oversized or malformed images before expensive image processing."""
    if not uploaded_file:
        return

    max_bytes = (
        settings.PROFILE_PHOTO_MAX_BYTES if max_bytes is None else max_bytes
    )
    max_pixels = (
        settings.PROFILE_PHOTO_MAX_PIXELS if max_pixels is None else max_pixels
    )

    if uploaded_file.size > max_bytes:
        raise forms.ValidationError(
            f'Ukuran gambar maksimal {max_bytes // (1024 * 1024)} MB.'
        )

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > max_pixels:
                raise forms.ValidationError(
                    'Resolusi gambar terlalu besar untuk diproses dengan aman.'
                )
            image.verify()
    except forms.ValidationError:
        raise
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise forms.ValidationError('File tidak dapat dibaca sebagai gambar yang valid.') from exc
    finally:
        uploaded_file.seek(0)
