import logging
from typing import Any, Dict

import requests


logger = logging.getLogger(__name__)

UKWELI_BASE_URL = "https://penguin27-ukweli-lens-api.hf.space"
UKWELI_VERIFY_PATH = "/api/verify/"


class UkweliClientError(Exception):
    pass


def verify_ukweli_claim(claim: str) -> Dict[str, Any]:
    if not claim:
        raise UkweliClientError("claim must not be empty")

    url = f"{UKWELI_BASE_URL}{UKWELI_VERIFY_PATH}"
    payload = {"claim": claim}

    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
    except requests.Timeout as exc:
        logger.warning("Ukweli API request timed out", exc_info=exc)
        raise UkweliClientError("Ukweli API request timed out") from exc
    except requests.RequestException as exc:
        logger.warning("Ukweli API request failed", exc_info=exc)
        raise UkweliClientError(f"Ukweli API request failed: {exc}") from exc

    if response.status_code == 400:
        raise UkweliClientError("Invalid request to Ukweli API (400)")
    if response.status_code == 503:
        raise UkweliClientError("Ukweli API is temporarily unavailable (503)")
    if response.status_code >= 500:
        raise UkweliClientError("Ukweli API internal error")

    try:
        return response.json()
    except ValueError as exc:
        raise UkweliClientError("Failed to decode Ukweli API response as JSON") from exc
