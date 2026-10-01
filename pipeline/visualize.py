from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import cv2
import numpy as np

from .types import OCRToken, RoomInstance


# ---------------------------------------------------------------------------
# Consistent colour map: every room label always gets the same colour.
# Colours are (B, G, R) for OpenCV and also exported as hex for the frontend.
# ---------------------------------------------------------------------------

ROOM_LABEL_COLORS_BGR: Dict[str, Tuple[int, int, int]] = {
    "Kitchen":          (0,   0,   255),   # #FF0000  red
    "Bedroom":          (255, 144, 30),    # #1E90FF  dodger blue
    "Master Bedroom":   (230, 100, 20),    # #1464E6  dark blue
    "Living":           (0,   200, 0),     # #00C800  green
    "Hall":             (0,   200, 200),   # #C8C800  yellow
    "Dining":           (0,   165, 255),   # #FFA500  orange
    "Toilet":           (200, 0,   200),   # #C800C8  magenta
    "Bathroom":         (200, 0,   200),   # #C800C8  magenta (alias)
    "Balcony":          (200, 200, 0),     # #00C8C8  cyan
    "Pooja":            (100, 50,  200),   # #C83264  pink-ish
    "Utility":          (100, 180, 100),   # #64B464  muted green
    "Store":            (80,  130, 180),   # #B48250  tan
    "Passage":          (180, 130, 80),    # #5082B4  steel blue
    "Lobby":            (140, 140, 60),    # #3C8C8C  teal
    "Staircase":        (60,  60,  180),   # #B43C3C  brick
    "Terrace":          (50,  180, 220),   # #DCB432  gold
    "Wash":             (180, 80,  180),   # #B450B4  plum
    "Dress":            (130, 100, 220),   # #DC6482  rose
}

# Fallback palette for labels not in the map above.
_FALLBACK_PALETTE_BGR: List[Tuple[int, int, int]] = [
    (255, 100, 100), (100, 255, 100), (100, 100, 255),
    (255, 255, 100), (255, 100, 255), (100, 255, 255),
    (180, 120, 60),  (60, 120, 180),  (180, 60, 120),
]

_dynamic_assignments: Dict[str, Tuple[int, int, int]] = {}


def _bgr_to_hex(bgr: Tuple[int, int, int]) -> str:
    """Convert (B,G,R) to #RRGGBB hex string."""
    return f"#{bgr[2]:02X}{bgr[1]:02X}{bgr[0]:02X}"


def get_room_color_bgr(label: str) -> Tuple[int, int, int]:
    """Return a consistent BGR colour for a room label."""
    # Normalise: title-case, strip whitespace
    key = label.strip().title()
    if key in ROOM_LABEL_COLORS_BGR:
        return ROOM_LABEL_COLORS_BGR[key]
    # Check partial matches (e.g. "Bed Room" -> "Bedroom")
    lower = key.lower().replace(" ", "")
    for canon, color in ROOM_LABEL_COLORS_BGR.items():
        if canon.lower().replace(" ", "") == lower:
            return color
    # Dynamic fallback
    if key not in _dynamic_assignments:
        idx = len(_dynamic_assignments) % len(_FALLBACK_PALETTE_BGR)
        _dynamic_assignments[key] = _FALLBACK_PALETTE_BGR[idx]
    return _dynamic_assignments[key]


def get_room_color_hex(label: str) -> str:
    """Return a consistent hex colour (#RRGGBB) for a room label."""
    return _bgr_to_hex(get_room_color_bgr(label))


def build_color_legend(rooms: List[RoomInstance]) -> List[Dict[str, str]]:
    """Build a de-duplicated colour legend for a list of rooms."""
    seen: Dict[str, str] = {}
    for room in rooms:
        label = room.label or room.class_name or "Unknown"
        if label not in seen:
            seen[label] = get_room_color_hex(label)
    return [{"label": lbl, "color": clr} for lbl, clr in seen.items()]


# ---------------------------------------------------------------------------
# Overlay drawing
# ---------------------------------------------------------------------------

def draw_final_overlay(image: np.ndarray, rooms: List[RoomInstance]) -> np.ndarray:
    vis = image.copy()
    overlay = vis.copy()
    for room in rooms:
        label_text = room.label or room.class_name
        color = get_room_color_bgr(label_text)
        pts = np.asarray(room.polygon_simplified.exterior.coords, dtype=np.int32)

        # Semi-transparent fill
        cv2.fillPoly(overlay, [pts], color)

        # Solid border
        cv2.polylines(vis, [pts], isClosed=True, color=color, thickness=2)

    # Blend filled overlay at 30 % opacity
    cv2.addWeighted(overlay, 0.30, vis, 0.70, 0, vis)

    # Draw labels on top (so they aren't tinted)
    for room in rooms:
        cx, cy = int(room.centroid[0]), int(room.centroid[1])
        label_text = room.label or room.class_name
        display = label_text
        if room.dimensions_text:
            display = f"{display} | {room.dimensions_text}"
        color = get_room_color_bgr(label_text)
        cv2.putText(vis, display[:64], (cx - 80, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(vis, display[:64], (cx - 80, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return vis


def draw_ocr_overlay(image: np.ndarray, tokens: Iterable[OCRToken]) -> np.ndarray:
    vis = image.copy()
    for tok in tokens:
        pts = np.asarray(tok.box, dtype=np.int32)
        cv2.polylines(vis, [pts], isClosed=True, color=(0, 180, 255), thickness=1)
        x = int(min(p[0] for p in tok.box))
        y = int(min(p[1] for p in tok.box)) - 2
        cv2.putText(vis, tok.text[:32], (x, max(12, y)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 180, 255), 1, cv2.LINE_AA)
    return vis


def save_debug_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)
