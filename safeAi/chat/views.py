import os
import uuid

import requests
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view

from .gemini_service import GeminiClientError, generate_gemini_response
from .models import APIUser, ChatUser, MessageLog, TelegramUser
from .serializers import (
    APIKeyRequestSerializer,
    APIMessageRequestSerializer,
    APIUserSerializer,
    ChatRequestSerializer,
    ChatUserSerializer,
    MessageLogSerializer,
    TelegramUserSerializer,
)


@api_view(["POST"])
def chat_view(request):
    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if not request.session.session_key:
        request.session.create()
    session_id = request.session.session_key

    chat_user, _ = ChatUser.objects.get_or_create(session_id=session_id)

    message = serializer.validated_data["message"]

    try:
        response_text = generate_gemini_response(message)
    except GeminiClientError as exc:
        MessageLog.objects.create(
            source="chat",
            chat_user=chat_user,
            request_text=message,
            response_text=str(exc),
        )
        return JsonResponse(
            {"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY
        )

    MessageLog.objects.create(
        source="chat",
        chat_user=chat_user,
        request_text=message,
        response_text=response_text,
    )

    return JsonResponse({"response": response_text})


@api_view(["POST"])
def api_generate_key_view(request):
    serializer = APIKeyRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    company_name = serializer.validated_data["company_name"]
    api_key = str(uuid.uuid4())

    api_user = APIUser.objects.create(company_name=company_name, api_key=api_key)

    return JsonResponse({"api_key": api_user.api_key})


@api_view(["POST"])
def api_message_view(request):
    serializer = APIMessageRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    api_key = serializer.validated_data["api_key"]
    message = serializer.validated_data["message"]

    try:
        api_user = APIUser.objects.get(api_key=api_key)
    except APIUser.DoesNotExist:
        MessageLog.objects.create(
            source="api",
            api_user=None,
            request_text=message,
            response_text="Invalid API key",
        )
        return JsonResponse(
            {"detail": "Invalid API key"}, status=status.HTTP_401_UNAUTHORIZED
        )

    try:
        response_text = generate_gemini_response(message)
    except GeminiClientError as exc:
        MessageLog.objects.create(
            source="api",
            api_user=api_user,
            request_text=message,
            response_text=str(exc),
        )
        return JsonResponse(
            {"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY
        )

    MessageLog.objects.create(
        source="api",
        api_user=api_user,
        request_text=message,
        response_text=response_text,
    )

    return JsonResponse({"response": response_text, "api_user_id": api_user.id})


@api_view(["POST"])
def telegram_webhook_view(request):
    data = request.data

    message = data.get("message") or {}
    chat = message.get("chat") or {}
    text = message.get("text")
    telegram_id = chat.get("id")
    username = chat.get("username") or chat.get("first_name")

    if telegram_id is None or text is None:
        return JsonResponse({"detail": "Invalid Telegram payload"}, status=400)

    telegram_user, _ = TelegramUser.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={"username": username},
    )

    if username and telegram_user.username != username:
        telegram_user.username = username
        telegram_user.save(update_fields=["username"])

    try:
        response_text = generate_gemini_response(text)
    except GeminiClientError as exc:
        response_text = "Sorry, I had an issue processing your request."
        MessageLog.objects.create(
            source="telegram",
            telegram_user=telegram_user,
            request_text=text,
            response_text=str(exc),
        )
    else:
        MessageLog.objects.create(
            source="telegram",
            telegram_user=telegram_user,
            request_text=text,
            response_text=response_text,
        )

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if bot_token:
        telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": telegram_id, "text": response_text}
        try:
            requests.post(telegram_url, json=payload, timeout=10)
        except requests.RequestException:
            pass

    return JsonResponse({"ok": True})


@api_view(["GET"])
def all_data_view(request):
    chat_users = ChatUserSerializer(ChatUser.objects.all(), many=True).data
    telegram_users = TelegramUserSerializer(TelegramUser.objects.all(), many=True).data
    api_users = APIUserSerializer(APIUser.objects.all(), many=True).data
    message_logs = MessageLogSerializer(MessageLog.objects.all(), many=True).data

    return JsonResponse(
        {
            "chat_users": chat_users,
            "telegram_users": telegram_users,
            "api_users": api_users,
            "message_logs": message_logs,
        },
        safe=False,
    )
