from shapely.geometry import Polygon

from pipeline.ocr_merge import merge_room_tokens
from pipeline.types import OCRToken


def _tok(text: str, x1: float, y1: float, x2: float, y2: float) -> OCRToken:
    box = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    return OCRToken(text=text, conf=0.9, box=box, box_poly=Polygon(box), box_bbox=(x1, y1, x2, y2))


def test_line_grouping_and_glue():
    tokens = [
        _tok("12'", 10, 10, 30, 20),
        _tok("-0\"", 31, 10, 47, 20),
        _tok("x", 55, 10, 62, 20),
        _tok("10'", 70, 10, 90, 20),
        _tok("-6\"", 91, 10, 108, 20),
    ]
    merged = merge_room_tokens(tokens)
    assert merged.ocr_lines
    assert "12'-0\"x10'-6\"" in merged.ocr_lines[0].replace(" ", "")
