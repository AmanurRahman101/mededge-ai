"""Live smoke test for the model endpoints MedEdge AI depends on.

Default checks spend a few cents: one Muse Spark 1.3 structured call, two SAM 3.1
concept prompts, and one 1.5 s Muse Voice Transcribe request. The glimmer check is
opt-in and hits your Colab tunnel instead of Meta.

Run from the repo root:
  backend\\.venv\\Scripts\\python scripts\\smoke_meta.py
  backend\\.venv\\Scripts\\python scripts\\smoke_meta.py --only sam --image path\\to\\report.jpg
  backend\\.venv\\Scripts\\python scripts\\smoke_meta.py --only glimmer
"""

import argparse
import asyncio
import io
import random
import sys
import time
import wave
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageOps
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.models.providers import ImagePart, TextPart
from app.models.router import ModelRouter
from app.pipeline.segment import parse_boxes, segment_concept
from app.pipeline.transcribe import transcribe_wav

OUT = Path(__file__).resolve().parent / "out"
DEFAULT_CHECKS = ("spark", "sam", "voice")
MAX_SIDE = 2000


class ArithmeticReply(BaseModel):
    status: str
    total: int


class TableCount(BaseModel):
    is_table_visible: bool
    data_rows: int


def synthetic_page() -> ImagePart:
    """A plain sheet with a header block and a ruled 6-row table. Contains no real data."""
    img = Image.new("RGB", (1200, 1600), (120, 120, 118))
    draw = ImageDraw.Draw(img)
    draw.rectangle((100, 80, 1100, 1520), fill=(250, 250, 246))
    draw.text((140, 120), "CITY DIAGNOSTIC CENTRE", fill=(20, 20, 20))
    draw.text((140, 170), "Name: ________   Age: __   Sex: _", fill=(20, 20, 20))
    top, left, right, row_h = 320, 140, 1060, 70
    columns = (left, 520, 700, 860, right)
    rows = [("Test", "Result", "Unit", "Ref. range")] + [
        ("Haemoglobin", "11.2", "g/dL", "13.0-17.0"),
        ("S. Creatinine", "1.4", "mg/dL", "0.7-1.2"),
        ("Platelets", "2.1", "lakh/cumm", "1.5-4.0"),
        ("ESR", "28", "mm/1st hr", "0-10"),
        ("WBC", "9,800", "/cumm", "4000-11000"),
        ("RBS", "7.9", "mmol/L", "<7.8"),
    ]
    for i, row in enumerate(rows):
        y = top + i * row_h
        draw.line((left, y, right, y), fill=(30, 30, 30), width=2)
        for x, cell in zip(columns, row, strict=False):
            draw.text((x + 12, y + 24), cell, fill=(20, 20, 20))
    bottom = top + len(rows) * row_h
    draw.line((left, bottom, right, bottom), fill=(30, 30, 30), width=2)
    for x in columns:
        draw.line((x, top, x, bottom), fill=(30, 30, 30), width=2)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return ImagePart(buffer.getvalue(), "image/png")


def load_image(path: Path) -> ImagePart:
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return ImagePart(buffer.getvalue(), "image/jpeg")


def quiet_wav(seconds: float = 1.5, rate: int = 24000) -> bytes:
    rng = random.Random(7)
    samples = bytearray()
    for _ in range(int(seconds * rate)):
        samples += int(rng.gauss(0, 60)).to_bytes(2, "little", signed=True)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(samples))
    return buffer.getvalue()


async def check_spark(http: httpx.AsyncClient, settings: Settings, **_) -> str:
    pinned = settings.model_copy(update={"role_structurer": "meta:muse-spark-1.3"})
    result = await ModelRouter(pinned, http).structured(
        "structurer",
        instructions="You are a connectivity test. Reply with JSON only.",
        parts=[TextPart("Set status to 'ok' and total to 17 + 25.")],
        schema=ArithmeticReply,
    )
    if result.value.total != 42:
        raise AssertionError(f"expected 42, got {result.value.total}")
    usage = result.usage
    return (
        f"{result.target} answered 42 in {result.latency_ms} ms "
        f"(in {usage.input_tokens} / out {usage.output_tokens} tokens)"
    )


async def check_sam(http: httpx.AsyncClient, settings: Settings, image: ImagePart, **_) -> str:
    OUT.mkdir(exist_ok=True)
    concepts = ("sheet of paper", "table")
    started = time.perf_counter()
    outputs = await asyncio.gather(
        *(segment_concept(http, settings, image, concept) for concept in concepts)
    )
    elapsed = int((time.perf_counter() - started) * 1000)
    summary = []
    for concept, raw in zip(concepts, outputs, strict=True):
        (OUT / f"sam_{concept.replace(' ', '_')}.txt").write_text(raw, encoding="utf-8")
        boxes = parse_boxes(raw)
        first = boxes[0] if boxes else None
        where = f" first box ({first.x1},{first.y1})-({first.x2},{first.y2})" if first else ""
        summary.append(f"'{concept}': {len(boxes)} match(es){where}")
    return f"{'; '.join(summary)} in {elapsed} ms. Raw output saved to scripts/out/"


async def check_voice(http: httpx.AsyncClient, settings: Settings, audio: bytes, **_) -> str:
    started = time.perf_counter()
    result = await transcribe_wav(http, settings, audio)
    elapsed = int((time.perf_counter() - started) * 1000)
    transcript = result.get("transcript", "")
    return f"{result.get('audioDurationMs')} ms of audio, transcript {transcript!r} in {elapsed} ms"


async def check_glimmer(http: httpx.AsyncClient, settings: Settings, image: ImagePart, **_) -> str:
    if not settings.endpoint("glimmer").configured:
        raise RuntimeError("GLIMMER_BASE_URL is empty; run colab/glimmer_server.ipynb first")
    pinned = settings.model_copy(update={"role_extractor": "glimmer:muse-glimmer"})
    result = await ModelRouter(pinned, http).structured(
        "extractor",
        instructions="You read lab report images. Reply with JSON only.",
        parts=[
            TextPart("Is a results table visible, and how many data rows (excluding header)?"),
            image,
        ],
        schema=TableCount,
    )
    return f"{result.target} saw {result.value} in {result.latency_ms} ms"


CHECKS = {
    "spark": check_spark,
    "sam": check_sam,
    "voice": check_voice,
    "glimmer": check_glimmer,
}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help=f"comma list from {', '.join(CHECKS)}")
    parser.add_argument("--image", type=Path, help="report photo for the sam and glimmer checks")
    parser.add_argument("--audio", type=Path, help="mono 16-bit PCM WAV at 16 or 24 kHz")
    args = parser.parse_args()

    settings = get_settings()
    selected = [c.strip() for c in args.only.split(",")] if args.only else list(DEFAULT_CHECKS)
    unknown = [c for c in selected if c not in CHECKS]
    if unknown:
        parser.error(f"unknown check(s): {', '.join(unknown)}")
    needs_meta = any(c != "glimmer" for c in selected)
    if needs_meta and not settings.model_api_key:
        print("MODEL_API_KEY is missing. Copy .env.example to .env and add your Meta key.")
        return 2

    inputs = {
        "image": load_image(args.image) if args.image else synthetic_page(),
        "audio": args.audio.read_bytes() if args.audio else quiet_wav(),
    }
    failures = 0
    timeout = httpx.Timeout(settings.request_timeout_s, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        for name in selected:
            try:
                detail = await CHECKS[name](http, settings, **inputs)
            except Exception as exc:  # noqa: BLE001 - report every failure and keep going
                failures += 1
                print(f"FAIL  {name:<8} {type(exc).__name__}: {exc}")
            else:
                print(f"PASS  {name:<8} {detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
