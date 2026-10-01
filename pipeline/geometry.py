from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from shapely.geometry import Polygon


@dataclass
class CropTransform:
    x1: int
    y1: int
    x2: int
    y2: int

    def to_global(self, x: float, y: float) -> Tuple[float, float]:
        return float(x + self.x1), float(y + self.y1)

    def to_local(self, x: float, y: float) -> Tuple[float, float]:
        return float(x - self.x1), float(y - self.y1)


def polygon_from_contour(contour: np.ndarray) -> Optional[Polygon]:
    if contour is None or len(contour) < 3:
        return None
    pts = contour.reshape(-1, 2)
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty or poly.area <= 1:
        return None
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda p: p.area)
    if poly.geom_type != "Polygon":
        return None
    return poly


def polygon_to_int_coords(polygon: Polygon) -> np.ndarray:
    coords = np.asarray(polygon.exterior.coords, dtype=np.float32)
    return np.round(coords).astype(np.int32)


def polygon_iou(poly_a: Polygon, poly_b: Polygon) -> float:
    inter = poly_a.intersection(poly_b).area
    if inter <= 0:
        return 0.0
    union = poly_a.union(poly_b).area
    if union <= 0:
        return 0.0
    return float(inter / union)


def bbox_from_polygon(polygon: Polygon) -> Tuple[int, int, int, int]:
    minx, miny, maxx, maxy = polygon.bounds
    return int(minx), int(miny), int(maxx), int(maxy)


def extract_room_crop(image: np.ndarray, polygon: Polygon, pad: int) -> Tuple[np.ndarray, CropTransform]:
    h, w = image.shape[:2]
    minx, miny, maxx, maxy = polygon.bounds
    x1 = max(0, int(np.floor(minx)) - pad)
    y1 = max(0, int(np.floor(miny)) - pad)
    x2 = min(w, int(np.ceil(maxx)) + pad)
    y2 = min(h, int(np.ceil(maxy)) + pad)
    crop = image[y1:y2, x1:x2].copy()
    return crop, CropTransform(x1=x1, y1=y1, x2=x2, y2=y2)


def polygon_global_to_local(polygon: Polygon, transform: CropTransform) -> np.ndarray:
    pts = []
    for x, y in polygon.exterior.coords:
        lx, ly = transform.to_local(x, y)
        pts.append([lx, ly])
    arr = np.asarray(pts, dtype=np.float32)
    return np.round(arr).astype(np.int32)


def mask_outside_polygon(crop_img: np.ndarray, polygon_local: np.ndarray) -> np.ndarray:
    if len(crop_img.shape) == 2:
        fill_color = 255
    else:
        fill_color = (255, 255, 255)
    out = np.full_like(crop_img, fill_color)
    mask = np.zeros(crop_img.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [polygon_local], 255)
    out[mask == 255] = crop_img[mask == 255]
    return out


def mask_to_polygon(mask: np.ndarray) -> Optional[Polygon]:
    mask_u8 = (mask > 0).astype(np.uint8) * 255
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    return polygon_from_contour(contour)


def box_polygon(points: List[Tuple[float, float]]) -> Polygon:
    poly = Polygon(points)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly
