from rest_framework import serializers

from .models import APIUser, ChatUser, MessageLog, TelegramUser


class ChatUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatUser
        fields = ["id", "session_id", "created_at"]


class TelegramUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramUser
        fields = ["id", "telegram_id", "username", "created_at"]


class APIUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = APIUser
        fields = ["id", "company_name", "api_key", "created_at"]


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField()


class APIMessageRequestSerializer(serializers.Serializer):
    api_key = serializers.CharField()
    message = serializers.CharField()


class APIKeyRequestSerializer(serializers.Serializer):
    company_name = serializers.CharField()


class MessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageLog
        fields = [
            "id",
            "source",
            "chat_user",
            "telegram_user",
            "api_user",
            "request_text",
            "response_text",
            "created_at",
        ]


class ChatUploadRequestSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField()
