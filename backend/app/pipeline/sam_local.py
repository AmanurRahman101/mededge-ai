import asyncio
from pathlib import Path

from app.models.providers import ImagePart, ProviderError
from app.pipeline.segment import SamBox


async def segment_local(
    image: ImagePart, concepts: tuple[str, ...], checkpoint: str
) -> dict[str, list[SamBox]]:
    """Run the open SAM 3.1 weights on this machine. The page never leaves the process."""
    path = Path(checkpoint) if checkpoint else None
    if path is None or not path.exists():
        raise ProviderError(
            "SAM_PROVIDER=local needs SAM_LOCAL_CHECKPOINT pointing at sam3.1_multiplex.pt "
            "(about 3.5 GB, from facebook/sam3.1). The Meta API mode is the default."
        )
    return await asyncio.to_thread(_segment_sync, image, concepts, path)


def _segment_sync(
    image: ImagePart, concepts: tuple[str, ...], checkpoint: Path
) -> dict[str, list[SamBox]]:
    try:
        import io

        import torch
        from PIL import Image
        from sam3.model.sam3_image_processor import Sam3Processor
        from sam3.model_builder import build_sam3_image_model
    except ImportError as exc:
        raise ProviderError(
            "Local SAM needs the sam3 package, PyTorch, and a CUDA or CPU build. "
            f"Import failed: {exc}"
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_sam3_image_model(
        checkpoint_path=str(checkpoint), load_from_HF=False, device=device
    )
    processor = Sam3Processor(model)
    pil = Image.open(io.BytesIO(image.data)).convert("RGB")
    width, height = pil.size
    found: dict[str, list[SamBox]] = {}
    for concept in concepts:
        state = processor.set_image(pil)
        output = processor.set_text_prompt(state=state, prompt=concept)
        boxes = output.get("boxes")
        scores = output.get("scores")
        found[concept] = _to_boxes(boxes, scores, width, height)
    return found


def _to_boxes(boxes, scores, width: int, height: int) -> list[SamBox]:
    if boxes is None:
        return []
    converted: list[SamBox] = []
    for index, box in enumerate(boxes):
        values = [float(v) for v in box]
        if len(values) < 4:
            continue
        score = float(scores[index]) if scores is not None else None
        converted.append(
            SamBox(
                object_id=index + 1,
                x1=round(values[0]),
                y1=round(values[1]),
                x2=round(values[2]),
                y2=round(values[3]),
                frame_w=width,
                frame_h=height,
                confidence=score,
            )
        )
    return converted
