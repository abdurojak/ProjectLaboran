"""
ASGI config for project_laboran project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.sessions import SessionMiddlewareStack
from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_laboran.settings')

django_asgi_app = get_asgi_application()

from project_laboran.routing import websocket_urlpatterns

websocket_application = SessionMiddlewareStack(URLRouter(websocket_urlpatterns))


async def prefixed_websocket_application(scope, receive, send):
    prefix = (settings.FORCE_SCRIPT_NAME or '').rstrip('/')
    if prefix and scope['path'].startswith(f'{prefix}/') and not scope.get('root_path'):
        scope = {**scope, 'root_path': prefix}
    await websocket_application(scope, receive, send)


application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': prefixed_websocket_application,
})
