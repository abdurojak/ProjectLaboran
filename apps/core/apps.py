from django.apps import AppConfig
from django.conf import settings


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        if not getattr(settings, 'LABHUB_LICENSE_ENFORCED', False):
            return

        from apps.core.licensing import enforce_configured_license

        enforce_configured_license()
