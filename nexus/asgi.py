"""
ASGI config for nexus project.

Exposes ASGI application for both HTTP and WebSocket protocols.
WebSocket connections use JWT token authentication via query string.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing consumers.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from api.middleware import JwtAuthMiddlewareStack
from api.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JwtAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
