# from django.urls import path
# from . import views
from django.http import JsonResponse

# urlpatterns = [
#     path('', views.homepage, name='homepage'),
#     path('check_login_status/', lambda r: JsonResponse({'is_logged_in': r.session.get('is_logged_in', False)})),
#     path('get-conversation/', views.recent_conversations, name='get_conversation'),
#     path('chat/<int:contact_id>/', views.chat_with_contact, name='chat_with_contact'),
#     path('chat_history/<int:dialog_id>/', views.get_chat_history, name='get_chat_history'),
#     path('send_message/', views.send_message, name='send_message'),
# ]

from django.urls import path
from . import views

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('check_login_status/', lambda r: (
        print(f"Check login status for session: {r.session.get('session_id')}"),
        JsonResponse({'is_logged_in': r.session.get('is_logged_in', False)})
    )[-1], name='check_login_status'),
    path('get-conversation/', views.recent_conversations, name='get_conversation'),
    path('chat/<int:contact_id>/', views.chat_with_contact, name='chat_with_contact'),
    path('chat_history/<int:dialog_id>/', views.get_chat_history, name='get_chat_history'),
    path('send_message/', views.send_message, name='send_message'),
]