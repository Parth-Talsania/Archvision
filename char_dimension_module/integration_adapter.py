"""
Standalone integration adapter (does not modify your existing pipeline).

Usage sketch:
    from char_dimension_module.integration_adapter import enrich_rooms_with_char_dimensions

    updated_rooms = enrich_rooms_with_char_dimensions(
        image=img,
        rooms=rooms,  # each room has "polygon_coordinates"
        char_model_path="weights/dim_char_yolov8n.pt",
        debug_dir="debug_chars",
    )
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from shapely.geometry import Polygon

from .dimension_char_reader import extract_room_dimensions


def _polygon_from_room(room: Dict) -> Optional[Polygon]:
    coords = room.get("polygon_coordinates") or room.get("polygon")
    if not coords or len(coords) < 3:
        return None
    try:
        pts = [(float(p[0]), float(p[1])) for p in coords]
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            return None
        return poly
    except Exception:
        return None


def enrich_rooms_with_char_dimensions(
    image: np.ndarray,
    rooms: List[Dict],
    char_model_path: str,
    debug_dir: Optional[str] = None,
    device: str = "cpu",
) -> List[Dict]:
    out: List[Dict] = []
    dpath = Path(debug_dir) if debug_dir else None
    if dpath is not None:
        dpath.mkdir(parents=True, exist_ok=True)

    for i, room in enumerate(rooms, start=1):
        r = dict(room)
        poly = _polygon_from_room(r)
        if poly is None:
            out.append(r)
            continue

        dbg_path = None
        if dpath is not None:
            dbg_path = str(dpath / f"room_{i:03d}_chars.png")

        res = extract_room_dimensions(
            image=image,
            room_polygon=poly,
            model_path=char_model_path,
            device=device,
            debug=dbg_path is not None,
            debug_path=dbg_path,
        )

        r["dimensions"] = res.dimensions_text
        r["dimensions_confidence"] = float(res.confidence)
        r["dimension_source"] = "char_detector"
        if res.parsed is not None:
            r["dimensions_parsed"] = {
                "a_inches": res.parsed.side_a_inches,
                "b_inches": res.parsed.side_b_inches,
                "area_sqft": res.parsed.area_sqft,
                "canonical": res.parsed.canonical_text,
            }
        else:
            r["dimensions_parsed"] = None

        out.append(r)

    return out
