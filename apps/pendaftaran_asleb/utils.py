from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse


def get_public_registration_url():
    base_url = settings.PUBLIC_ACCESS_BASE_URL.rstrip('/') + '/'
    return urljoin(base_url, reverse('pendaftaran_asleb:pendaftaran_public').lstrip('/'))
