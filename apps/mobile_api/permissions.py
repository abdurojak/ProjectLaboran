from rest_framework.permissions import BasePermission

from apps.asleb.models import Asleb


class IsAsistenLab(BasePermission):
    message = 'Akun tidak memiliki akses sebagai Asisten Lab.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and getattr(request.user, 'role', None) == 'asisten_lab'
            and Asleb.objects.filter(nim=request.user.nim_nik, status='aktif').exists()
        )
