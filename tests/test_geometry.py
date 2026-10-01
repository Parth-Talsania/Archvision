import numpy as np
from shapely.geometry import Polygon

from pipeline.geometry import CropTransform, extract_room_crop, polygon_from_contour


def test_polygon_validity_repair():
    # Bow-tie contour (self-intersection) should be repaired.
    contour = np.array([[[10, 10]], [[40, 40]], [[10, 40]], [[40, 10]]], dtype=np.int32)
    poly = polygon_from_contour(contour)
    assert poly is not None
    assert poly.is_valid


def test_crop_transform_roundtrip():
    img = np.zeros((100, 120, 3), dtype=np.uint8)
    poly = Polygon([(20, 20), (80, 20), (80, 70), (20, 70)])
    crop, tfm = extract_room_crop(img, poly, pad=10)
    assert crop.shape[0] > 0 and crop.shape[1] > 0
    gx, gy = tfm.to_global(5, 7)
    lx, ly = tfm.to_local(gx, gy)
    assert abs(lx - 5) < 1e-6
    assert abs(ly - 7) < 1e-6
