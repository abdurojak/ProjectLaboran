from django import forms


def validate_human_face_photo(uploaded_file):
    if not uploaded_file:
        return

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
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    if len(faces) < 1:
        raise forms.ValidationError(
            'Foto harus menampilkan wajah manusia yang jelas. Gambar anime, pemandangan, atau objek lain tidak bisa digunakan.'
        )
