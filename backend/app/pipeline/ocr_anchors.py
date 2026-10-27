import re
from dataclasses import dataclass

import numpy as np

_LABEL = re.compile(
    r"\b(name|patient|age|sex|gender|mobile|phone|cell|reg\.?|mrn|address|nid)\b",
    re.I,
)
_PHONE = re.compile(r"(?:\+?880[\s-]?)?01[3-9][\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{3}\b")
_ID = re.compile(r"\b(?:id|reg\.?|mrn|patient\s*id)\s*[:#]?\s*[A-Z0-9-]{4,}\b", re.I)


@dataclass(frozen=True)
class TextBox:
    x1: int
    y1: int
    x2: int
    y2: int
    text: str


def _engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None
    return RapidOCR()


def read_text_boxes(image_bgr: np.ndarray) -> list[TextBox]:
    engine = _engine()
    if engine is None:
        return []
    result, _elapsed = engine(image_bgr)
    boxes: list[TextBox] = []
    for item in result or []:
        points, text, _score = item[0], str(item[1]), item[2]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        boxes.append(TextBox(int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)), text))
    return boxes


def identifier_boxes(text_boxes: list[TextBox]) -> list[TextBox]:
    found: list[TextBox] = []
    for box in text_boxes:
        if _LABEL.search(box.text) or _PHONE.search(box.text) or _ID.search(box.text):
            found.append(box)
    return found
