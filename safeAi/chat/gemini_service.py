import os
from typing import Any, Dict

import requests


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")
GEMINI_API_BASE = os.environ.get(
    "GEMINI_API_BASE",
    "https://generativelanguage.googleapis.com/v1beta",
)


class GeminiClientError(Exception):
    pass


def generate_gemini_response(message: str) -> str:
    if not GEMINI_API_KEY:
        raise GeminiClientError("GEMINI_API_KEY is not configured")

    url = f"{GEMINI_API_BASE}/models/{GEMINI_MODEL_NAME}:generateContent"
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    payload: Dict[str, Any] = {
        "contents": [
            {
                "parts": [
                    {"text": message},
                ]
            }
        ]
    }

    response = requests.post(url, headers=headers, params=params, json=payload, timeout=30)
    if response.status_code != 200:
        raise GeminiClientError(
            f"Gemini API error {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiClientError(f"Unexpected Gemini response format: {data}") from exc
