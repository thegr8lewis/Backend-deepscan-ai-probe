from django.urls import path

from .views import (
    api_generate_key_view,
    api_message_view,
    all_data_view,
    chat_upload_view,
    chat_view,
    telegram_webhook_view,
    delete_message_log_view,
    ukweli_verify_view,
)


urlpatterns = [
    path("chat/", chat_view, name="chat"),
    path("chat/upload/", chat_upload_view, name="chat-upload"),
    path("telegram/webhook/", telegram_webhook_view, name="telegram-webhook"),
    path("api/generate-key/", api_generate_key_view, name="api-generate-key"),
    path("api/message/", api_message_view, name="api-message"),
    path("api/all-data/", all_data_view, name="api-all-data"),
    path("api/ukweli/verify/", ukweli_verify_view, name="ukweli-verify"),
    path("api/messages/<int:message_id>/", delete_message_log_view, name="delete-message-log"),
]
