from django.db import models


class ChatUser(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class APIUser(models.Model):
    company_name = models.CharField(max_length=255)
    api_key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MessageLog(models.Model):
    SOURCE_CHOICES = [
        ("chat", "Chat"),
        ("telegram", "Telegram"),
        ("api", "API"),
        ("ukweli", "Ukweli"),
    ]

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    chat_user = models.ForeignKey(
        ChatUser, null=True, blank=True, on_delete=models.SET_NULL, related_name="messages"
    )
    telegram_user = models.ForeignKey(
        TelegramUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="messages",
    )
    api_user = models.ForeignKey(
        APIUser, null=True, blank=True, on_delete=models.SET_NULL, related_name="messages"
    )
    request_text = models.TextField()
    response_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
