from channels.generic.websocket import AsyncWebsocketConsumer
import json

class SessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        await self.channel_layer.group_add(f"session_{self.session_id}", self.channel_name)
        await self.accept()
        print(f"WebSocket connected: session_{self.session_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(f"session_{self.session_id}", self.channel_name)
        print(f"WebSocket disconnected: session_{self.session_id}")

    async def new_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "new_message",
            "message": event["message"],
            "sender_id": event["sender_id"],
            "timestamp": event["timestamp"],
        }))

    async def login_success(self, event):
        await self.send(text_data=json.dumps({
            "type": "login_success",
            "is_logged_in": event["is_logged_in"],
        }))