import json

import httpx

from app.config import Settings
from app.models.providers import ImagePart
from app.pipeline.segment import SamBox, parse_boxes, segment_concept


def test_parses_boxes_with_and_without_confidence():
    line = (
        "<0f>1<|box;x1=444;y1=625;x2=679;y2=850;w=1800;h=1200;c=0.9609375|>"
        "<|mask;x=0;y=0;c=0.9609375;data=226,236,!AbC|>,"
        "2<|box;x1=10;y1=20;x2=30;y2=40;w=1800;h=1200|><|mask;x=0;y=0;data=1,2,!x|>"
    )
    assert parse_boxes(line) == [
        SamBox(1, 444, 625, 679, 850, 1800, 1200, 0.9609375),
        SamBox(2, 10, 20, 30, 40, 1800, 1200, None),
    ]


def test_zero_matches_is_an_empty_result():
    assert parse_boxes("") == []


async def test_streamed_box_survives_arbitrary_delta_boundaries():
    fragments = ["<0f>1<|bo", "x;x1=10;y1=", "20;x2=30;y2=40;w=100;h=80|>"]
    events = [
        "data: " + json.dumps({"type": "response.output_text.delta", "delta": part})
        for part in fragments
    ]
    events.append('data: {"type":"response.completed"}')
    body = "\n\n".join(events) + "\n\n"
    seen = []

    def handle(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    settings = Settings(_env_file=None, model_api_key="test-key")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        raw = await segment_concept(client, settings, ImagePart(b"synthetic"), "table")
    assert parse_boxes(raw) == [SamBox(1, 10, 20, 30, 40, 100, 80, None)]
    assert seen[0]["model"] == "sam-3.1"
    assert seen[0]["store"] is False
