import json
from pathlib import Path

from app.config import REPO_ROOT

SAMPLES = REPO_ROOT / "data" / "samples"
PRIVATE_RAW = REPO_ROOT / "data" / "private" / "raw"


def list_cases() -> list[dict]:
    manifest = SAMPLES / "manifest.json"
    if not manifest.exists():
        return []
    return json.loads(manifest.read_text(encoding="utf-8"))["cases"]


def load_case(case_id: str) -> dict | None:
    return next((case for case in list_cases() if case["id"] == case_id), None)


def case_image(case_id: str) -> tuple[bytes, str] | None:
    case = load_case(case_id)
    if case is None:
        return None
    path = SAMPLES / case["file"]
    if not path.exists():
        return None
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return path.read_bytes(), mime


def private_inbox() -> list[str]:
    if not PRIVATE_RAW.exists():
        return []
    return sorted(
        path.name
        for path in PRIVATE_RAW.iterdir()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )


def read_private(name: str) -> Path | None:
    path = (PRIVATE_RAW / name).resolve()
    if path.parent != PRIVATE_RAW.resolve() or not path.is_file():
        return None
    return path
