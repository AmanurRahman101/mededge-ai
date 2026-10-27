import json
from typing import Any

import httpx

from app.config import Settings
from app.models.providers import ProviderError

LANGUAGE_BIAS = ("Bengali", "English")

# Terms clinicians in Bangladesh say in mixed Bangla-English dictation.
CLINICAL_KEYWORDS = (
    "CBC",
    "ESR",
    "HbA1c",
    "creatinine",
    "S. creatinine",
    "lipid profile",
    "SGPT",
    "TSH",
    "fasting",
    "nephrology",
    "cardiology",
    "OPD",
    "follow-up",
    "specimen",
    "prescription",
)


async def transcribe_wav(
    http: httpx.AsyncClient,
    settings: Settings,
    wav: bytes,
    *,
    mode: str = "PUSH_TO_TALK",
    language_bias: tuple[str, ...] = LANGUAGE_BIAS,
    keywords: tuple[str, ...] = CLINICAL_KEYWORDS,
) -> dict[str, Any]:
    """Transcribe a mono 16-bit PCM WAV (16 or 24 kHz, under 10 min, under 32 MB)."""
    if not settings.model_api_key:
        raise ProviderError("MODEL_API_KEY is not set")
    request = {
        "model": settings.voice_model,
        "audioEncoding": "WAV",
        "mode": mode,
        "languageBias": list(language_bias),
        "keywords": list(keywords),
    }
    files = {
        "request": (None, json.dumps(request), "application/json"),
        "audio": ("audio.wav", wav, "audio/wav"),
    }
    headers = {
        "Authorization": f"Bearer {settings.model_api_key.get_secret_value()}",
        "Accept": "application/json",
    }
    try:
        response = await http.post(
            f"{settings.meta_base_url.rstrip('/')}/asr/transcribe", files=files, headers=headers
        )
    except httpx.TimeoutException as exc:
        raise ProviderError("Voice Transcribe timed out", retryable=True) from exc
    except httpx.TransportError as exc:
        raise ProviderError(f"Voice Transcribe unreachable: {exc}", retryable=True) from exc
    if not response.is_success:
        raise ProviderError(
            f"Voice Transcribe HTTP {response.status_code}: {response.text[:300]}",
            status=response.status_code,
            retryable=response.status_code == 429 or response.status_code >= 500,
        )
    return response.json()
