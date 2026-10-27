from app.pipeline.segment import SamBox, parse_boxes


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
