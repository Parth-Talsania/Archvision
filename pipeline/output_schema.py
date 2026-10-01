from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from .config import PipelineConfig
from .types import RoomInstance


def _poly_coords(room: RoomInstance) -> List[List[float]]:
    return [[round(float(x), 2), round(float(y), 2)] for x, y in room.polygon_simplified.exterior.coords]


def _room_to_dict(room: RoomInstance, include_ocr_raw: bool, include_text_debug: bool) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "id": room.id,
        "name": room.label or room.class_name,
        "label": room.label,
        "label_confidence": round(room.label_confidence, 4),
        "dimensions": room.dimensions_text,
        "dimensions_text": room.dimensions_text,
        "dimension_parsed": None,
        "area_text": room.area_text,
        "area_ft2": None if room.area_ft2 is None else round(float(room.area_ft2), 4),
        "area_pixels": round(float(room.area_px2), 2),
        "area_px2": round(float(room.area_px2), 2),
        "yolo_confidence": round(float(room.yolo_conf), 4),
        "centroid": {"x": round(float(room.centroid[0]), 2), "y": round(float(room.centroid[1]), 2)},
        "polygon_coordinates": _poly_coords(room),
    }
    if room.dimension_parsed is not None:
        p = room.dimension_parsed
        d["dimension_parsed"] = {
            "raw": p.raw,
            "formatted": p.formatted,
            "w_ft": p.w_ft,
            "w_in": p.w_in,
            "h_ft": p.h_ft,
            "h_in": p.h_in,
            "w_total_ft": p.w_total_ft,
            "h_total_ft": p.h_total_ft,
            "confidence": round(float(p.confidence), 4),
        }
    if include_ocr_raw:
        d["ocr_raw"] = [
            {
                "text": t.text,
                "conf": round(float(t.conf), 4),
                "source": t.source,
                "box_global": [[round(float(x), 2), round(float(y), 2)] for x, y in t.box],
                "bbox_global": [round(float(v), 2) for v in t.box_bbox],
                "meta": t.meta,
            }
            for t in room.ocr_tokens
        ]
    if include_text_debug:
        d["ocr_lines"] = room.ocr_lines
        d["ocr_merged_text"] = room.ocr_merged_text
    return d


def build_output(
    image_path: str,
    image: np.ndarray,
    rooms: List[RoomInstance],
    config: PipelineConfig,
    include_text_debug: bool = False,
    text_meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    h, w = image.shape[:2]
    return {
        "image": {
            "filename": Path(image_path).name,
            "path": str(image_path),
            "width": int(w),
            "height": int(h),
        },
        "model": {
            "yolo_model_path": config.model_path,
            "ocr_engine": config.ocr.engine,
            "pipeline_version": config.pipeline_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "total_rooms": len(rooms),
        "rooms": [_room_to_dict(r, include_ocr_raw=config.include_ocr_raw, include_text_debug=include_text_debug) for r in rooms],
        "text_metadata": text_meta or {},
    }
