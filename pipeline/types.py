from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from shapely.geometry import Polygon


@dataclass
class OCRToken:
    text: str
    conf: float
    box: List[Tuple[float, float]]
    box_poly: Polygon
    box_bbox: Tuple[float, float, float, float]
    source: str = "ocr"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DimensionParseResult:
    raw: str
    w_ft: int
    w_in: int
    h_ft: int
    h_in: int
    w_total_ft: float
    h_total_ft: float
    formatted: str
    confidence: float = 0.0


@dataclass
class AreaParseResult:
    raw: str
    value: float
    unit: str
    sqft: Optional[float]


@dataclass
class RoomInstance:
    id: int
    yolo_conf: float
    mask: np.ndarray
    polygon: Polygon
    polygon_simplified: Polygon
    bbox: Tuple[int, int, int, int]
    centroid: Tuple[float, float]
    area_px2: float
    class_name: str = "room"
    label: Optional[str] = None
    label_confidence: float = 0.0
    dimensions_text: Optional[str] = None
    dimension_parsed: Optional[DimensionParseResult] = None
    area_text: Optional[str] = None
    area_ft2: Optional[float] = None
    ocr_tokens: List[OCRToken] = field(default_factory=list)
    ocr_lines: List[str] = field(default_factory=list)
    ocr_merged_text: str = ""
    meta: Dict[str, str] = field(default_factory=dict)
