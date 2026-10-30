import io

import pytest
from PIL import Image

from app.pipeline.orchestrator import validate_image_size


def image_bytes(size):
    out = io.BytesIO()
    Image.new("RGB", size, "white").save(out, format="PNG")
    return out.getvalue()


def test_image_size_guard_accepts_sample_sized_image_and_rejects_large_image():
    validate_image_size(image_bytes((1402, 1884)))
    with pytest.raises(ValueError, match="3 megapixels"):
        validate_image_size(image_bytes((3000, 2000)))


def test_ocr_uses_bounded_working_size_and_preserves_box_coordinates(monkeypatch):
    import numpy as np
    import rapidocr_onnxruntime

    from app.pipeline.ocr_anchors import read_text_boxes

    options = {}

    class FakeOCR:
        def __init__(self, **kwargs):
            options.update(kwargs)

        def __call__(self, image):
            assert image.shape[:2] == (1884, 1402)
            return [([[100, 200], [300, 200], [300, 250], [100, 250]], "Name", 0.9)], 0

    monkeypatch.setattr(rapidocr_onnxruntime, "RapidOCR", FakeOCR)
    boxes = read_text_boxes(np.zeros((1884, 1402, 3), dtype=np.uint8))
    assert options["max_side_len"] == 1200
    assert (boxes[0].x1, boxes[0].y1, boxes[0].x2, boxes[0].y2) == (100, 200, 300, 250)


def test_real_bounded_ocr_finds_identifier_on_fictional_prescription():
    from pathlib import Path

    import cv2
    import numpy as np

    from app.pipeline.ocr_anchors import identifier_boxes, read_text_boxes

    sample = Path(__file__).resolve().parents[2] / "data" / "samples" / "prescription.png"
    image = cv2.imdecode(np.frombuffer(sample.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
    boxes = identifier_boxes(read_text_boxes(image))
    assert boxes
    assert all(0 <= box.x1 < box.x2 <= image.shape[1] for box in boxes)
    assert all(0 <= box.y1 < box.y2 <= image.shape[0] for box in boxes)
