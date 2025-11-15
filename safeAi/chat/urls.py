from django.urls import path

from .views import (
    api_generate_key_view,
    api_message_view,
    all_data_view,
    chat_upload_view,
    chat_view,
    telegram_webhook_view,
)


urlpatterns = [
    path("chat/", chat_view, name="chat"),
    path("chat/upload/", chat_upload_view, name="chat-upload"),
    path("telegram/webhook/", telegram_webhook_view, name="telegram-webhook"),
    path("api/generate-key/", api_generate_key_view, name="api-generate-key"),
    path("api/message/", api_message_view, name="api-message"),
    path("api/all-data/", all_data_view, name="api-all-data"),
]
