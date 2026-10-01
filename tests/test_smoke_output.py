import numpy as np
from shapely.geometry import Polygon

from pipeline.config import PipelineConfig
from pipeline.output_schema import build_output
from pipeline.types import RoomInstance


def test_output_has_required_keys():
    cfg = PipelineConfig(model_path="dummy.pt")
    room = RoomInstance(
        id=1,
        yolo_conf=0.9,
        mask=np.zeros((10, 10), dtype=np.uint8),
        polygon=Polygon([(1, 1), (5, 1), (5, 5), (1, 5)]),
        polygon_simplified=Polygon([(1, 1), (5, 1), (5, 5), (1, 5)]),
        bbox=(1, 1, 5, 5),
        centroid=(3.0, 3.0),
        area_px2=16.0,
    )
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    out = build_output("x.png", img, [room], cfg)
    assert "image" in out
    assert "model" in out
    assert "rooms" in out
    assert "label" in out["rooms"][0]
    assert "dimensions_text" in out["rooms"][0]
