import os
import asyncio
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from telegram.routing import websocket_urlpatterns
from telegram.views import telegram_manager
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'telegram_chat.settings')

django.setup()
django_asgi_app = get_asgi_application()

async def application(scope, receive, send):
    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                await telegram_manager.disconnect()
                await send({'type': 'lifespan.shutdown.complete'})
                break
    else:
        await ProtocolTypeRouter({
            'http': django_asgi_app,
            'websocket': URLRouter(websocket_urlpatterns),
        })(scope, receive, send)