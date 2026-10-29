import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from app.pipeline.ocr_anchors import TextBox
from app.pipeline.segment import SamBox

IDENTIFIER_CONCEPTS = ("barcode", "QR code", "signature", "stamp", "photo")


@dataclass(frozen=True)
class Redaction:
    redacted_png: bytes
    overlay_png: bytes
    table_png: bytes | None
    page_box: tuple[int, int, int, int]
    table_box: tuple[int, int, int, int] | None
    hidden_boxes: list[tuple[int, int, int, int]]


def _decode(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not read the uploaded image")
    return image


def _encode_png(image_bgr: np.ndarray) -> bytes:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    buffer = io.BytesIO()
    Image.fromarray(rgb).save(buffer, format="PNG")
    return buffer.getvalue()


def _clip(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    x1, x2 = sorted((max(0, x1), min(width - 1, x2)))
    y1, y2 = sorted((max(0, y1), min(height - 1, y2)))
    return x1, y1, max(x1 + 1, x2), max(y1 + 1, y2)


def _largest(boxes: list[SamBox]) -> SamBox | None:
    if not boxes:
        return None
    return max(boxes, key=lambda box: (box.x2 - box.x1) * (box.y2 - box.y1))


def _blur(image: np.ndarray, box: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    region = image[y1:y2, x1:x2]
    if region.size == 0:
        return
    height, width = region.shape[:2]
    # Pixelate before the blur so a short identifier line cannot be read back.
    tiny = cv2.resize(
        region,
        (max(1, width // 28), max(1, height // 8)),
        interpolation=cv2.INTER_LINEAR,
    )
    pixelated = cv2.resize(tiny, (width, height), interpolation=cv2.INTER_NEAREST)
    kernel = max(31, (min(height, width) // 2) | 1)
    image[y1:y2, x1:x2] = cv2.GaussianBlur(pixelated, (kernel, kernel), 0)


def _paint(
    overlay: np.ndarray, box: tuple[int, int, int, int], color: tuple[int, int, int]
) -> None:
    x1, y1, x2, y2 = box
    area = overlay[y1:y2, x1:x2]
    tint = np.full_like(area, color)
    cv2.addWeighted(tint, 0.35, area, 0.65, 0, dst=area)
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, thickness=2)


def redact(
    image_bytes: bytes,
    regions: dict[str, list[SamBox]],
    anchors: list[TextBox],
) -> Redaction:
    """Blur the header band and identifier marks. The table crop is the only region kept sharp."""
    image = _decode(image_bytes)
    height, width = image.shape[:2]
    paper = _largest(regions.get("sheet of paper", []))
    page = (
        _clip((paper.x1, paper.y1, paper.x2, paper.y2), width, height)
        if paper
        else (0, 0, width, height)
    )
    px1, py1, px2, py2 = page
    page_image = image[py1:py2, px1:px2].copy()
    page_h, page_w = page_image.shape[:2]

    table = _largest(regions.get("table", []))
    table_box: tuple[int, int, int, int] | None = None
    if table is not None:
        table_box = _clip(
            (table.x1 - px1, table.y1 - py1, table.x2 - px1, table.y2 - py1), page_w, page_h
        )

    hidden: list[tuple[int, int, int, int]] = []
    if table_box is not None and table_box[1] > 8:
        hidden.append((0, 0, page_w, table_box[1]))
    elif table_box is None and not anchors:
        # No table and no printed identifier line: hide a short top band.
        hidden.append((0, 0, page_w, max(1, int(page_h * 0.22))))

    for concept in IDENTIFIER_CONCEPTS:
        for box in regions.get(concept, []):
            hidden.append(
                _clip((box.x1 - px1, box.y1 - py1, box.x2 - px1, box.y2 - py1), page_w, page_h)
            )
    pad = 8
    for anchor in anchors:
        hidden.append(
            _clip(
                (
                    anchor.x1 - px1 - pad,
                    anchor.y1 - py1 - pad,
                    anchor.x2 - px1 + pad,
                    anchor.y2 - py1 + pad,
                ),
                page_w,
                page_h,
            )
        )

    redacted = page_image.copy()
    for box in hidden:
        _blur(redacted, box)

    overlay = page_image.copy()
    for box in hidden:
        _paint(overlay, box, (48, 48, 210))
    if table_box is not None:
        _paint(overlay, table_box, (70, 160, 70))

    table_png = (
        _encode_png(redacted[table_box[1] : table_box[3], table_box[0] : table_box[2]])
        if table_box
        else None
    )
    return Redaction(
        redacted_png=_encode_png(redacted),
        overlay_png=_encode_png(overlay),
        table_png=table_png,
        page_box=page,
        table_box=table_box,
        hidden_boxes=hidden,
    )
