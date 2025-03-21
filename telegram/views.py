import asyncio
from asgiref.sync import sync_to_async
from django.shortcuts import render, redirect
import uuid
from channels.layers import get_channel_layer
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest

from .models import Contact, Chat, Conversation

class TelegramManager:
    _clients = {}

    async def get_client(self, session_id):
        if session_id not in self._clients or not self._clients[session_id].is_connected():
            client = TelegramClient(session_id, 26593961, "c973c24001c8655b6fde04783dce2c41")
            await client.connect()
            if await client.is_user_authorized():
                self._setup_event_handlers(client, session_id)
            self._clients[session_id] = client
        return self._clients[session_id]

    def _setup_event_handlers(self, client, session_id):
        @client.on(events.NewMessage)
        async def handle_new_message(event):
            print("__________________", event)
            # breakpoint()
            contact, _ = await sync_to_async(Contact.objects.get_or_create)(
                session_id=session_id, user_id=event.sender_id,
                defaults={'first_name': '', 'last_name': '', 'phone': 'Unknown'}
            )
            await sync_to_async(Chat.objects.create)(
                session_id=session_id,
                contact=contact,
                message_id=event.message.id,
                message_text=event.message.message or "",
                timestamp=event.message.date,
                is_sent=event.message.out,
            )
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f"session_{session_id}",
                {
                    "type": "new_message",
                    "message": event.message.message or "",
                    "sender_id": str(event.sender_id),
                    "timestamp": event.message.date.isoformat(),
                }
            )

    async def disconnect(self):
        for client in self._clients.values():
            if client.is_connected():
                await client.disconnect()
        self._clients.clear()

telegram_manager = TelegramManager()

async def homepage(request):
    session_id = request.session.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session['session_id'] = session_id
        request.session['is_logged_in'] = False
        await sync_to_async(request.session.save)()
        print(f"New session created: {session_id}, session_key: {request.session.session_key}, is_logged_in: {request.session['is_logged_in']}")

    client = await telegram_manager.get_client(session_id)
    if await client.is_user_authorized():
        print(f"User authorized for session {session_id}, session_key: {request.session.session_key}, redirecting...")
        return redirect(reverse('get_conversation'))

    print(f"Session {session_id} before QR login: session_key: {request.session.session_key}, is_logged_in = {request.session.get('is_logged_in')}")
    qr_login = await client.qr_login()
    asyncio.create_task(wait_for_login(qr_login, request, session_id))
    return render(request, 'homepage.html', {'qr_url': qr_login.url, 'session_id': session_id})

async def wait_for_login(qr_login, request, session_id):
    while True:
        try:
            await qr_login.wait(10)
            # Synchronous session update
            def update_session():
                request.session['is_logged_in'] = True
                request.session.modified = True
                request.session.save()
            await sync_to_async(update_session)()
            print(f"Session {session_id} updated: session_key: {request.session.session_key}, is_logged_in = {request.session['is_logged_in']}")
            channel_layer = get_channel_layer()
            print(f"Sending login_success to session_{session_id}")
            await channel_layer.group_send(
                f"session_{session_id}",
                {"type": "login_success", "is_logged_in": True}
            )
            break
        except Exception as e:
            print(f"QR login recreate: {e}")
            await qr_login.recreate()

async def recent_conversations(request):
    session_id = await sync_to_async(lambda: request.session.get('session_id'))()
    is_logged_in = await sync_to_async(lambda: request.session.get('is_logged_in', False))()
    
    if not session_id or not is_logged_in:
        return await sync_to_async(lambda: redirect(reverse('homepage')))()

    client = await telegram_manager.get_client(session_id)
    conversations = await sync_to_async(lambda: list(Conversation.objects.filter(session_id=session_id)))()
    if not conversations:
        dialogs = await client.get_dialogs(limit=None)
        print(f"Fetched {len(dialogs)} dialogs from Telegram for session {session_id}")
        current_user_id = (await client.get_me()).id
        
        saved_contacts = 0
        saved_conversations = 0
        
        for i, dialog in enumerate(dialogs, 1):
            entity = dialog.entity
            print(f"Processing dialog {i}/{len(dialogs)}: {dialog.id} - {dialog.name}")
            
            if not hasattr(entity, 'id'):
                print(f"Skipping dialog {dialog.name}: no entity ID")
                continue
            
            # Contact creation
            try:
                first_name = getattr(entity, 'first_name', None) or getattr(entity, 'title', None) or ''
                contact, created = await sync_to_async(Contact.objects.get_or_create)(
                    session_id=session_id,
                    user_id=entity.id,
                    defaults={
                        'first_name': first_name,
                        'last_name': getattr(entity, 'last_name', None) or '',
                        'phone': getattr(entity, 'phone', None) or 'Unknown',
                    }
                )
                if created:
                    saved_contacts += 1
                    print(f"Created contact: {entity.id} - {first_name}")
                else:
                    print(f"Existing contact: {entity.id} - {first_name}")
            except Exception as e:
                print(f"Error creating contact for dialog {dialog.id} ({dialog.name}): {e}")
                continue

            # Fetch messages with timeout
            try:
                messages = await asyncio.wait_for(client.get_messages(entity, limit=50), timeout=10.0)
                print(f"Fetched {len(messages)} messages for dialog {dialog.id}")
            except asyncio.TimeoutError:
                print(f"Timeout fetching messages for dialog {dialog.id} ({dialog.name})")
                messages = []
            except Exception as e:
                print(f"Error fetching messages for dialog {dialog.id} ({dialog.name}): {e}")
                messages = []

            # Save messages
            for message in messages:
                try:
                    await sync_to_async(Chat.objects.update_or_create)(
                        session_id=session_id,
                        contact=contact,
                        message_id=message.id,
                        defaults={
                            'message_text': message.message or '',
                            'timestamp': message.date,
                            'is_sent': message.sender_id == current_user_id,
                        }
                    )
                except Exception as e:
                    print(f"Error saving message {message.id} for dialog {dialog.id}: {e}")
                    continue

            # Save conversation
            try:
                last_message = dialog.message.message or "No message"
                if len(last_message) > 30:
                    last_message = last_message[:30] + "..."
                await sync_to_async(Conversation.objects.update_or_create)(
                    session_id=session_id,
                    dialog_id=dialog.id,
                    contact=contact,
                    defaults={
                        'name': dialog.name or 'Unknown',
                        'last_message': last_message,
                        'timestamp': str(dialog.message.date) if dialog.message else '...',
                        'unread_count': dialog.unread_count,
                    }
                )
                saved_conversations += 1
                print(f"Saved conversation: {dialog.id} - {dialog.name}")
            except Exception as e:
                print(f"Error saving conversation {dialog.id} ({dialog.name}): {e}")
                continue
        
        conversations = await sync_to_async(lambda: list(Conversation.objects.filter(session_id=session_id)))()
        print(f"Processed {saved_contacts} contacts and {saved_conversations} conversations")
        print(f"Database has {len(conversations)} conversations for session {session_id}")

    print(f"Rendering response for session {session_id}")
    response = await sync_to_async(lambda: render(request, 'recent_conversations.html', {
        'conversations': conversations,
        'session_id': session_id
    }))()
    print(f"Response sent for session {session_id}")
    return response

async def chat_with_contact(request, contact_id):
    session_id = request.session.get('session_id')
    if not session_id or not request.session.get('is_logged_in'):
        return redirect(reverse('homepage'))

    client = await telegram_manager.get_client(session_id)
    try:
        contact = await sync_to_async(Contact.objects.get)(id=contact_id, session_id=session_id)
    except Contact.DoesNotExist:
        return redirect(reverse('recent_conversations'))

    chats = await sync_to_async(lambda: list(Chat.objects.filter(session_id=session_id, contact=contact)))()
    if not chats:
        history = await client(GetHistoryRequest(
            peer=contact.user_id,
            limit=100,
            offset_id=0,
            offset_date=None,
            add_offset=0,
            max_id=0,
            min_id=0,
            hash=0
        ))
        current_user_id = (await client.get_me()).id
        for message in history.messages:
            await sync_to_async(Chat.objects.update_or_create)(
                session_id=session_id,
                contact=contact,
                message_id=message.id,
                defaults={
                    'message_text': message.message or '',
                    'timestamp': message.date,
                    'is_sent': message.sender_id == current_user_id,
                }
            )
        chats = await sync_to_async(lambda: list(Chat.objects.filter(session_id=session_id, contact=contact)))()

    return render(request, 'chat_with_contact.html', {'contact': contact, 'chats': chats, 'session_id': session_id})

async def get_chat_history(request, dialog_id):
    session_id = await sync_to_async(lambda: request.session.get("session_id"))()
    print(f"Session data: {await sync_to_async(lambda: dict(request.session.items()))()}")
    if not session_id:
        return await sync_to_async(lambda: JsonResponse({'error': 'Not authenticated'}, status=401))()

    # Fetch messages for the given dialog_id
    messages = await sync_to_async(lambda: list(
        Chat.objects.filter(session_id=session_id, contact__conversations__dialog_id=dialog_id)
        .order_by('timestamp')
    ))()

    messages_data = [
        {
            'id': msg.message_id,
            'text': msg.message_text,
            'timestamp': str(msg.timestamp),
            'is_sent': msg.is_sent,
        }
        for msg in messages
    ]

    return await sync_to_async(lambda: JsonResponse({'messages': messages_data}))()

async def send_message(request):
    # Log entry
    print("Entering send_message")

    # Check method
    method = await sync_to_async(lambda: request.method)()
    if method != 'POST':
        print("Invalid method:", method)
        return await sync_to_async(lambda: JsonResponse({'error': 'Invalid request method'}, status=400))()

    # Session checks
    session_id = await sync_to_async(lambda: request.session.get('session_id'))()
    is_logged_in = await sync_to_async(lambda: request.session.get('is_logged_in'))()
    print(f"Session ID: {session_id}, Logged In: {is_logged_in}")
    if not session_id or not is_logged_in:
        print("Not authenticated")
        return await sync_to_async(lambda: JsonResponse({'error': 'Not authenticated'}, status=401))()

    # POST data
    dialog_id = await sync_to_async(lambda: request.POST.get('dialog_id'))()
    message_text = await sync_to_async(lambda: request.POST.get('message_text'))()
    print(f"Dialog ID: {dialog_id}, Message: {message_text}")
    if not dialog_id or not message_text:
        print("Missing parameters")
        return await sync_to_async(lambda: JsonResponse({'error': 'Missing parameters'}, status=400))()

    # Telegram client
    print("Getting Telegram client")
    client = await telegram_manager.get_client(session_id)

    # Fetch conversation
    print(f"Fetching conversation for dialog_id: {dialog_id}")
    conversation = await sync_to_async(lambda: Conversation.objects.get(session_id=session_id, dialog_id=dialog_id))()
    contact = await sync_to_async(lambda: conversation.contact)()  # Ensure contact access is wrapped
    print(f"Got conversation: {conversation.name}, Contact: {contact.user_id}")

    # Send message
    print("Sending message via Telegram")
    message = await client.send_message(contact.user_id, message_text)
    print(f"Message sent, ID: {message.id}")

    # Save chat
    print("Saving chat message")
    await sync_to_async(lambda: Chat.objects.create(
        session_id=session_id,
        contact=contact,
        message_id=message.id,
        message_text=message_text,
        timestamp=message.date,
        is_sent=True,
    ))()

    # Update conversation
    last_message = message_text if len(message_text) <= 30 else message_text[:30] + "..."
    print("Updating conversation")
    await sync_to_async(lambda: Conversation.objects.update_or_create(
        session_id=session_id,
        dialog_id=dialog_id,
        contact=contact,
        defaults={
            'name': conversation.name,
            'last_message': last_message,
            'timestamp': str(message.date),
            'unread_count': 0,
        }
    ))()
    # NOTE: This is a simplified version of the update_or_create method. In production, you should handle the case where the conversation already exists.
    # # WebSocket update
    # print("Sending WebSocket update")
    # channel_layer = get_channel_layer()
    # await channel_layer.group_send(
    #     f"session_{session_id}",
    #     {
    #         "type": "new_message",
    #         "message": message_text,
    #         "sender_id": str(contact.user_id),
    #         "timestamp": str(message.date),
    #     }
    # )

    # Response
    print("Returning response")
    return await sync_to_async(lambda: JsonResponse({
        'success': True,
        'message': {
            'id': message.id,
            'text': message_text,
            'timestamp': str(message.date),
            'is_sent': True,
        }
    }))()