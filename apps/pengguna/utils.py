from django import forms

from apps.core.upload_validators import validate_safe_image_upload


# Known non-photographic avatar reported by a user. This is a near-duplicate
# check, not a general AI-image detector.
BLOCKED_AVATAR_HASHES = (0x3133B399C3E30D5B,)


def image_perceptual_hash(gray_image, cv2):
    import numpy as np

    low_frequency = cv2.dct(cv2.resize(gray_image, (32, 32)).astype(np.float32))[:8, :8]
    median = np.median(low_frequency[1:, :])
    return sum(int(value > median) << index for index, value in enumerate(low_frequency.flat))


def matches_blocked_avatar(gray_image, cv2):
    fingerprint = image_perceptual_hash(gray_image, cv2)
    return any((fingerprint ^ blocked).bit_count() <= 6 for blocked in BLOCKED_AVATAR_HASHES)


def validate_human_face_photo(uploaded_file):
    if not uploaded_file:
        return

    validate_safe_image_upload(uploaded_file)

    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise forms.ValidationError(
            'Validasi wajah belum aktif karena OpenCV belum terinstall. Jalankan pip install -r requirements.txt.'
        ) from exc

    data = np.frombuffer(uploaded_file.read(), np.uint8)
    uploaded_file.seek(0)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)

    if image is None:
        raise forms.ValidationError('File foto tidak bisa dibaca sebagai gambar.')

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if matches_blocked_avatar(gray, cv2):
        raise forms.ValidationError('Gunakan foto wajah asli, bukan avatar atau ilustrasi.')

    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    if len(faces) < 1:
        raise forms.ValidationError(
            'Foto harus menampilkan wajah manusia yang jelas. Gambar anime, pemandangan, atau objek lain tidak bisa digunakan.'
        )
