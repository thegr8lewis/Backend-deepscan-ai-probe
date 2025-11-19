import json
import os
import uuid

import requests
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser

from .gemini_service import GeminiClientError, generate_gemini_response
from .models import APIUser, ChatUser, MessageLog, TelegramUser
from .ukweli_service import UkweliClientError, verify_ukweli_claim
from .serializers import (
    APIKeyRequestSerializer,
    APIMessageRequestSerializer,
    APIUserSerializer,
    ChatRequestSerializer,
    ChatUploadRequestSerializer,
    ChatUserSerializer,
    MessageLogSerializer,
    UkweliVerifyRequestSerializer,
    TelegramUserSerializer,
)


def _extract_text_from_uploaded_file(uploaded_file):
    name = (uploaded_file.name or "").lower()
    if name.endswith(".pdf"):
        from PyPDF2 import PdfReader

        reader = PdfReader(uploaded_file)
        parts = []
        for page in reader.pages:
            text = page.extract_text() or ""
            parts.append(text)
        return "\n".join(parts)
    if name.endswith(".docx") or name.endswith(".doc"):
        from docx import Document

        document = Document(uploaded_file)
        parts = [p.text for p in document.paragraphs if p.text]
        return "\n".join(parts)
    # Fallback: treat as text file
    data = uploaded_file.read()
    try:
        return data.decode("utf-8", errors="ignore")
    except AttributeError:
        return str(data)


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
@parser_classes([MultiPartParser, FormParser])
def chat_upload_view(request):
    serializer = ChatUploadRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if not request.session.session_key:
        request.session.create()
    session_id = request.session.session_key

    chat_user, _ = ChatUser.objects.get_or_create(session_id=session_id)

    message = serializer.validated_data.get("message") or ""
    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        return JsonResponse({"file": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

    try:
        extracted_text = _extract_text_from_uploaded_file(uploaded_file)
    except Exception as exc:  # noqa: BLE001
        MessageLog.objects.create(
            source="chat",
            chat_user=chat_user,
            request_text=message or uploaded_file.name,
            response_text=f"Failed to extract file text: {exc}",
        )
        return JsonResponse(
            {"detail": "Failed to read uploaded file."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    combined_text = (message + "\n\n" + extracted_text).strip() if message else extracted_text

    try:
        response_text = generate_gemini_response(combined_text)
    except GeminiClientError as exc:
        MessageLog.objects.create(
            source="chat",
            chat_user=chat_user,
            request_text=combined_text,
            response_text=str(exc),
        )
        return JsonResponse(
            {"detail": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    MessageLog.objects.create(
        source="chat",
        chat_user=chat_user,
        request_text=combined_text,
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
        result = verify_ukweli_claim(text)

        verdict = result.get("final_verdict", "UNKNOWN")
        score = result.get("explainable_confidence_score")
        snippet = result.get("top_evidence_snippet") or {}

        evidence_verdict = snippet.get("verdict")
        evidence_text = snippet.get("evidence")
        evidence_source = snippet.get("source")

        parts = [f"Verdict: {verdict}"]
        if isinstance(score, (int, float)):
            parts.append(f"Confidence: {score:.2f}")

        if evidence_verdict or evidence_text or evidence_source:
            parts.append("")
            parts.append("Top evidence:")
            if evidence_verdict:
                parts.append(f"- Stance: {evidence_verdict}")
            if evidence_text:
                parts.append(f"- Evidence: {evidence_text}")
            if evidence_source:
                parts.append(f"- Source: {evidence_source}")

        response_text = "\n".join(parts)

        MessageLog.objects.create(
            source="ukweli",
            telegram_user=telegram_user,
            request_text=text,
            response_text=json.dumps(result),
        )
    except UkweliClientError as exc:
        response_text = "Sorry, I had an issue verifying that claim. Please try again later."
        MessageLog.objects.create(
            source="ukweli",
            telegram_user=telegram_user,
            request_text=text,
            response_text=str(exc),
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


@api_view(["GET"])
def health_check_view(request):
    return JsonResponse({"status": "ok"})


@api_view(["DELETE"])
def delete_message_log_view(request, message_id):
    try:
        log = MessageLog.objects.get(id=message_id)
    except MessageLog.DoesNotExist:
        return JsonResponse({"detail": "MessageLog not found"}, status=status.HTTP_404_NOT_FOUND)

    log.delete()
    return JsonResponse({}, status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
def ukweli_verify_view(request):
    serializer = UkweliVerifyRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    api_key = serializer.validated_data["api_key"]
    claim = serializer.validated_data["claim"]

    try:
        api_user = APIUser.objects.get(api_key=api_key)
    except APIUser.DoesNotExist:
        MessageLog.objects.create(
            source="ukweli",
            api_user=None,
            request_text=claim,
            response_text="Invalid API key",
        )
        return JsonResponse(
            {"detail": "Invalid API key"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        result = verify_ukweli_claim(claim)
    except UkweliClientError as exc:
        MessageLog.objects.create(
            source="ukweli",
            api_user=api_user,
            request_text=claim,
            response_text=str(exc),
        )
        return JsonResponse({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    MessageLog.objects.create(
        source="ukweli",
        api_user=api_user,
        request_text=claim,
        response_text=json.dumps(result),
    )

    return JsonResponse(result)
