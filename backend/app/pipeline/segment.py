import asyncio
import json
import re
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.models.providers import ImagePart, ProviderError

_BOX = re.compile(r"(\d+)<\|box;([^|]*)\|>")


@dataclass(frozen=True)
class SamBox:
    object_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    frame_w: int
    frame_h: int
    confidence: float | None


def parse_boxes(output_text: str) -> list[SamBox]:
    """Read box records from SAM 3.1 output, e.g. `<0f>1<|box;x1=..;y1=..;w=..;h=..;c=..|>`.

    Coordinates are inclusive pixels in the submitted image. Masks are decoded separately.
    """
    boxes: list[SamBox] = []
    for match in _BOX.finditer(output_text):
        fields = dict(kv.split("=", 1) for kv in match.group(2).split(";") if "=" in kv)
        boxes.append(
            SamBox(
                object_id=int(match.group(1)),
                x1=round(float(fields["x1"])),
                y1=round(float(fields["y1"])),
                x2=round(float(fields["x2"])),
                y2=round(float(fields["y2"])),
                frame_w=int(fields["w"]),
                frame_h=int(fields["h"]),
                confidence=float(fields["c"]) if "c" in fields else None,
            )
        )
    return boxes


CONCEPTS = ("sheet of paper", "table", "barcode", "QR code", "signature", "stamp", "photo")


async def segment_page(
    http: httpx.AsyncClient, settings: Settings, image: ImagePart
) -> dict[str, list[SamBox]]:
    if settings.sam_provider == "local":
        from app.pipeline.sam_local import segment_local

        return await segment_local(image, CONCEPTS, settings.sam_local_checkpoint)
    raw = await asyncio.gather(
        *(segment_concept(http, settings, image, concept) for concept in CONCEPTS)
    )
    return {concept: parse_boxes(text) for concept, text in zip(CONCEPTS, raw, strict=True)}


async def segment_concept(
    http: httpx.AsyncClient, settings: Settings, image: ImagePart, concept: str
) -> str:
    """Stream one SAM 3.1 concept prompt and return the raw output text.

    SAM takes one short noun phrase per request; callers fan out concepts in parallel.
    """
    if settings.sam_provider != "meta":
        raise NotImplementedError("Local SAM 3.1 edge mode is not wired up yet")
    if not settings.model_api_key:
        raise ProviderError("MODEL_API_KEY is not set")

    body = {
        "model": settings.sam_model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": concept},
                    {"type": "input_image", "image_url": image.data_url},
                ],
            }
        ],
        "stream": True,
        "store": False,
        "metadata": {"include_confidence": "true", "mask_encoding": "one_bit"},
    }
    headers = {
        "Authorization": f"Bearer {settings.model_api_key.get_secret_value()}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    chunks: list[str] = []
    try:
        async with http.stream(
            "POST", f"{settings.meta_base_url.rstrip('/')}/responses", json=body, headers=headers
        ) as response:
            if not response.is_success:
                detail = (await response.aread()).decode("utf-8", errors="replace")[:300]
                raise ProviderError(
                    f"SAM HTTP {response.status_code}: {detail}",
                    status=response.status_code,
                    retryable=response.status_code == 429 or response.status_code >= 500,
                )
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line.removeprefix("data: ").strip()
                if payload == "[DONE]":
                    break
                event = json.loads(payload)
                kind = event.get("type")
                if kind == "response.output_text.delta":
                    chunks.append(event.get("delta", ""))
                elif kind in ("response.failed", "error"):
                    raise ProviderError(f"SAM stream failed: {str(event)[:300]}")
                elif kind == "response.completed":
                    break
    except httpx.TimeoutException as exc:
        raise ProviderError("SAM timed out", retryable=True) from exc
    except httpx.TransportError as exc:
        raise ProviderError(f"SAM unreachable: {exc}", retryable=True) from exc
    # Deltas are arbitrary fragments, not complete lines. Inserting separators
    # can split SAM's box markers or coordinate fields and lose detections.
    return "".join(chunks)
