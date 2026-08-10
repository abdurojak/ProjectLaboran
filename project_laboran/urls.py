"""
URL configuration for project_laboran project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
import re

from django.urls import include, path, re_path
from django.conf import settings
from django.http import JsonResponse
from django.views.static import serve as serve_media
from apps.pengguna.views import SchoolSearchView

urlpatterns = [
    path('health/', lambda request: JsonResponse({'status': 'ok'}), name='health'),
    path('api/profile/education/schools/search/', SchoolSearchView.as_view(), name='school_search_global'),
    path('api/mobile/v1/', include('apps.mobile_api.urls')),
    path('', include('apps.dashboard.urls')),
    path('asleb/', include('apps.asleb.urls')),
    path('barang-tertinggal/', include('apps.barang_tertinggal.urls')),
    path('inventaris/', include('apps.inventaris.urls')),
    path('jadwal/', include('apps.jadwal.urls')),
    path('kalender/', include('apps.kalender.urls')),
    path('peminjaman/', include('apps.peminjaman.urls')),
    path('pendaftaran-asleb/', include('apps.pendaftaran_asleb.urls')),
    path('pengguna/', include('apps.pengguna.urls')),
    path('pengaturan/', include('apps.core.urls')),
    path('ruangan/', include('apps.ruangan.urls')),
    path('surat/', include('apps.surat.urls')),
    path('admin/', admin.site.urls),
]

# Uploads must always pass through PenggunaLoginRequiredMiddleware. Serving
# MEDIA_ROOT directly from the reverse proxy would bypass document ownership
# checks for transcripts, attendance evidence, reports, and payment receipts.
media_prefix = settings.MEDIA_URL.strip('/')
if media_prefix:
    urlpatterns.append(
        re_path(
            rf'^{re.escape(media_prefix)}/(?P<path>.*)$',
            serve_media,
            {'document_root': settings.MEDIA_ROOT, 'show_indexes': False},
        )
    )
