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
