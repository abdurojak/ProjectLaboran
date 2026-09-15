from .settings import *  # noqa: F403


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_project_laboran.sqlite3',  # noqa: F405
    },
}

# Test uploads must never depend on a workstation or production-mounted media drive.
MEDIA_ROOT = BASE_DIR / 'tmp' / 'test-media'  # noqa: F405

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
LABHUB_LICENSE_ENFORCED = False
