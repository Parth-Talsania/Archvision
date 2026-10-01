"""
Character-level dimension extraction module for floor plans.

Run (inference example):
    from shapely.geometry import Polygon
    import cv2
    from char_dimension_module.dimension_char_reader import extract_room_dimensions

    img = cv2.imread("plan.png")
    poly = Polygon([(10, 10), (200, 10), (200, 150), (10, 150)])
    out = extract_room_dimensions(
        image=img,
        room_polygon=poly,
        model_path="weights/dim_char_yolov8n.pt",
        debug=False,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import math
import re

import cv2
import numpy as np
from shapely.geometry import Point, Polygon

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None


CHAR_CLASS_NAMES: List[str] = [
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "apostrophe",
    "quote",
    "slash",
    "dash",
    "x",
    "dot",
    "times",
    "half",
    "quarter",
    "three_quarter",
]

CLASS_TO_EMIT: Dict[str, str] = {
    "0": "0",
    "1": "1",
    "2": "2",
    "3": "3",
    "4": "4",
    "5": "5",
    "6": "6",
    "7": "7",
    "8": "8",
    "9": "9",
    "apostrophe": "'",
    "quote": '"',
    "slash": "/",
    "dash": "-",
    "x": "x",
    "dot": ".",
    "times": "x",
    "half": "1/2",
    "quarter": "1/4",
    "three_quarter": "3/4",
}


@dataclass
class CropTransform:
    x1: int
    y1: int
    scale: float

    def to_global(self, x: float, y: float) -> Tuple[float, float]:
        return (x / self.scale) + float(self.x1), (y / self.scale) + float(self.y1)


@dataclass
class CharDet:
    cls_name: str
    conf: float
    bbox_xyxy: Tuple[float, float, float, float]
    cx: float
    cy: float
    w: float
    h: float


@dataclass
class ParsedMeasurement:
    feet: int
    inches: int
    frac_num: int = 0
    frac_den: int = 1
    total_inches: float = 0.0
    canonical: str = ""


@dataclass
class ParsedDimension:
    raw_text: str
    canonical_text: str
    side_a_inches: float
    side_b_inches: Optional[float]
    area_sqft: Optional[float]
    dimension_confidence: float


@dataclass
class RoomDimensionResult:
    dimensions_text: Optional[str]
    parsed: Optional[ParsedDimension]
    confidence: float
    source: str
    candidates: List[Tuple[str, float]] = field(default_factory=list)


_MODEL_CACHE: Dict[str, object] = {}


def _get_model(model_path: str):
    if YOLO is None:
        raise RuntimeError("ultralytics is not installed")
    key = str(Path(model_path))
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = YOLO(key)
    return _MODEL_CACHE[key]


def _to_int_polygon_coords(polygon: Polygon, transform: CropTransform) -> np.ndarray:
    pts: List[List[int]] = []
    for x, y in polygon.exterior.coords:
        lx = int(round((x - transform.x1) * transform.scale))
        ly = int(round((y - transform.y1) * transform.scale))
        pts.append([lx, ly])
    return np.asarray(pts, dtype=np.int32)


def _extract_masked_room_crop(
    image: np.ndarray,
    room_polygon: Polygon,
    pad: int = 30,
    upscale: float = 2.0,
) -> Tuple[np.ndarray, CropTransform]:
    h, w = image.shape[:2]
    minx, miny, maxx, maxy = room_polygon.bounds
    x1 = max(0, int(math.floor(minx)) - pad)
    y1 = max(0, int(math.floor(miny)) - pad)
    x2 = min(w, int(math.ceil(maxx)) + pad)
    y2 = min(h, int(math.ceil(maxy)) + pad)

    crop = image[y1:y2, x1:x2].copy()
    transform = CropTransform(x1=x1, y1=y1, scale=upscale)

    local_poly = _to_int_polygon_coords(room_polygon, CropTransform(x1=x1, y1=y1, scale=1.0))
    mask = np.zeros(crop.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [local_poly], 255)

    masked = np.full_like(crop, 255)
    masked[mask == 255] = crop[mask == 255]

    if upscale != 1.0:
        new_w = max(2, int(round(masked.shape[1] * upscale)))
        new_h = max(2, int(round(masked.shape[0] * upscale)))
        masked = cv2.resize(masked, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    return masked, transform


def detect_chars(
    image: np.ndarray,
    model_path: str,
    conf: float = 0.25,
    imgsz: int = 1024,
    device: str = "cpu",
    tile_size: Optional[int] = None,
    tile_overlap: int = 96,
) -> List[CharDet]:
    """Detect character boxes on image. Supports optional tiled inference."""
    model = _get_model(model_path)

    if tile_size is None or (image.shape[0] <= tile_size and image.shape[1] <= tile_size):
        return _predict_chars_on_patch(model, image, conf=conf, imgsz=imgsz, device=device, offset=(0, 0))

    out: List[CharDet] = []
    h, w = image.shape[:2]
    step = max(64, tile_size - tile_overlap)
    for y in range(0, h, step):
        for x in range(0, w, step):
            patch = image[y:min(h, y + tile_size), x:min(w, x + tile_size)]
            if patch.size == 0:
                continue
            out.extend(_predict_chars_on_patch(model, patch, conf=conf, imgsz=imgsz, device=device, offset=(x, y)))

    return _nms_chars(out, iou_threshold=0.45)


def _predict_chars_on_patch(model, patch: np.ndarray, conf: float, imgsz: int, device: str, offset: Tuple[int, int]) -> List[CharDet]:
    results = model.predict(source=patch, conf=conf, imgsz=imgsz, device=device, verbose=False)
    if not results:
        return []
    result = results[0]
    if result.boxes is None:
        return []

    cls_names = result.names if hasattr(result, "names") else {i: n for i, n in enumerate(CHAR_CLASS_NAMES)}
    boxes_xyxy = result.boxes.xyxy.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    clss = result.boxes.cls.cpu().numpy().astype(int)

    ox, oy = offset
    dets: List[CharDet] = []
    for b, c, ci in zip(boxes_xyxy, confs, clss):
        x1, y1, x2, y2 = float(b[0] + ox), float(b[1] + oy), float(b[2] + ox), float(b[3] + oy)
        w = max(0.0, x2 - x1)
        h = max(0.0, y2 - y1)
        if w <= 0 or h <= 0:
            continue
        dets.append(
            CharDet(
                cls_name=str(cls_names.get(int(ci), str(ci))),
                conf=float(c),
                bbox_xyxy=(x1, y1, x2, y2),
                cx=(x1 + x2) / 2.0,
                cy=(y1 + y2) / 2.0,
                w=w,
                h=h,
            )
        )
    return dets


def _bbox_iou(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _nms_chars(dets: List[CharDet], iou_threshold: float) -> List[CharDet]:
    dets_sorted = sorted(dets, key=lambda d: d.conf, reverse=True)
    keep: List[CharDet] = []
    for d in dets_sorted:
        if all(_bbox_iou(d.bbox_xyxy, k.bbox_xyxy) < iou_threshold for k in keep):
            keep.append(d)
    return keep


def group_into_lines(dets: Sequence[CharDet]) -> List[List[CharDet]]:
    if not dets:
        return []
    heights = [max(1.0, d.h) for d in dets]
    hmed = float(np.median(np.asarray(heights, dtype=np.float32)))

    sorted_dets = sorted(dets, key=lambda d: d.cy)
    lines: List[List[CharDet]] = []
    line_cys: List[float] = []

    for d in sorted_dets:
        placed = False
        for i, cy in enumerate(line_cys):
            if abs(d.cy - cy) <= 0.6 * hmed:
                lines[i].append(d)
                line_cys[i] = float(np.mean([x.cy for x in lines[i]]))
                placed = True
                break
        if not placed:
            lines.append([d])
            line_cys.append(d.cy)

    for line in lines:
        line.sort(key=lambda d: d.cx)
    return lines


def line_to_text(line_dets: Sequence[CharDet]) -> Tuple[str, float]:
    if not line_dets:
        return "", 0.0

    sorted_line = sorted(line_dets, key=lambda d: d.cx)
    widths = [max(1.0, d.w) for d in sorted_line]
    wmed = float(np.median(np.asarray(widths, dtype=np.float32)))

    out_parts: List[str] = []
    confs: List[float] = []

    for i, d in enumerate(sorted_line):
        if i > 0:
            prev = sorted_line[i - 1]
            gap = d.bbox_xyxy[0] - prev.bbox_xyxy[2]
            if gap > 0.8 * wmed:
                out_parts.append(" ")
        out_parts.append(CLASS_TO_EMIT.get(d.cls_name, ""))
        confs.append(d.conf)

    text = "".join(out_parts)
    base_conf = float(np.mean(confs)) if confs else 0.0

    penalty = 0.0
    if not re.search(r"\d", text):
        penalty += 0.35
    if "x" not in text and "'" not in text and '"' not in text and "/" not in text:
        penalty += 0.25
    conf = max(0.0, base_conf * (1.0 - penalty))
    return text, conf


def _line_dimension_likeness(text: str) -> float:
    score = 0.0
    if re.search(r"\d", text):
        score += 0.4
    if text.count("'") + text.count('"') > 0:
        score += 0.3
    if "x" in text.lower():
        score += 0.2
    if "/" in text:
        score += 0.1
    return min(1.0, score)


def merge_lines_to_candidates(lines: Sequence[Sequence[CharDet]]) -> List[Tuple[str, float]]:
    candidates: List[Tuple[str, float]] = []
    for line in lines:
        text, conf = line_to_text(line)
        like = _line_dimension_likeness(text)
        if like >= 0.4:
            candidates.append((text, conf * like))

    if len(lines) >= 2:
        line_texts = [line_to_text(line) for line in lines]
        for i in range(len(line_texts) - 1):
            t = (line_texts[i][0].strip() + " " + line_texts[i + 1][0].strip()).strip()
            c = (line_texts[i][1] + line_texts[i + 1][1]) / 2.0
            like = _line_dimension_likeness(t)
            if like >= 0.5:
                candidates.append((t, c * like))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:3]


def normalize_dimension_text(text: str) -> str:
    s = text.strip()
    s = s.replace("\u00d7", "x").replace("X", "x")
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201d", '"').replace("\u201c", '"')
    s = s.replace("\u00bd", "1/2").replace("\u00bc", "1/4").replace("\u00be", "3/4")
    s = re.sub(r"\s+", " ", s)

    # normalize feet-inch separator around dash
    s = re.sub(r"(\d+)\s*'\s*-\s*(\d+)", r"\1'-\2", s)
    s = re.sub(r"(\d+)'\s+(\d+)", r"\1'-\2", s)
    s = re.sub(r"(\d+)'(\d+)", r"\1'-\2", s)
    s = re.sub(r"(\d+)'\s*-\s*(\d+)-((?:1|3)/(?:2|4|8|16))", r"\1'-\2 \3", s)
    s = re.sub(r"(\d)(1/2|1/4|3/4)", r"\1 \2", s)

    # collapse accidental double separators
    s = re.sub(r"-+", "-", s)
    s = re.sub(r"\s*x\s*", " x ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_fraction(frac_text: str) -> Tuple[int, int]:
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", frac_text.strip())
    if not m:
        return (0, 1)
    num, den = int(m.group(1)), int(m.group(2))
    if den not in {2, 4, 8, 16}:
        return (0, 1)
    if num < 0 or num > den:
        return (0, 1)
    return (num, den)


def _measurement_to_canonical(feet: int, inches: int, frac_num: int, frac_den: int) -> str:
    if frac_num > 0:
        return f"{feet}'-{inches} {frac_num}/{frac_den}\""
    return f"{feet}'-{inches}\""


def parse_single_measurement(text: str) -> Optional[ParsedMeasurement]:
    s = normalize_dimension_text(text)

    # Try strict feet'-inch frac"
    m = re.search(r"(\d+)\s*'\s*-?\s*(\d+)(?:\s+(\d+\s*/\s*\d+))?\s*\"?", s)
    if not m:
        # fallback: feet only like 12'
        m2 = re.search(r"(\d+)\s*'", s)
        if not m2:
            return None
        feet = int(m2.group(1))
        inches = 0
        frac_num, frac_den = 0, 1
    else:
        feet = int(m.group(1))
        inches = int(m.group(2))
        frac_num, frac_den = (0, 1)
        if m.group(3):
            frac_num, frac_den = _parse_fraction(m.group(3))

    total_inches = feet * 12.0 + inches + (float(frac_num) / float(frac_den))
    canonical = _measurement_to_canonical(feet, inches, frac_num, frac_den)
    return ParsedMeasurement(
        feet=feet,
        inches=inches,
        frac_num=frac_num,
        frac_den=frac_den,
        total_inches=total_inches,
        canonical=canonical,
    )


def parse_dimension_candidate(text: str, char_conf: float = 1.0) -> Optional[ParsedDimension]:
    normalized = normalize_dimension_text(text)
    if not normalized:
        return None

    sides = [x.strip() for x in re.split(r"\bx\b", normalized) if x.strip()]
    if not sides:
        return None

    a = parse_single_measurement(sides[0])
    if a is None:
        return None

    b: Optional[ParsedMeasurement] = None
    if len(sides) >= 2:
        b = parse_single_measurement(sides[1])

    if b is not None:
        canonical = f"{a.canonical} x {b.canonical}"
        area_sqft = round((a.total_inches * b.total_inches) / 144.0, 4)
        parse_factor = 1.0
        side_b_inches: Optional[float] = b.total_inches
    else:
        canonical = a.canonical
        area_sqft = None
        parse_factor = 0.7
        side_b_inches = None

    dim_conf = max(0.0, min(1.0, char_conf * parse_factor))

    return ParsedDimension(
        raw_text=text,
        canonical_text=canonical,
        side_a_inches=a.total_inches,
        side_b_inches=side_b_inches,
        area_sqft=area_sqft,
        dimension_confidence=dim_conf,
    )


def draw_debug_chars(
    image: np.ndarray,
    dets: Sequence[CharDet],
    reconstructed_lines: Sequence[str],
    parsed_text: Optional[str],
) -> np.ndarray:
    out = image.copy()
    for d in dets:
        x1, y1, x2, y2 = [int(round(v)) for v in d.bbox_xyxy]
        cv2.rectangle(out, (x1, y1), (x2, y2), (40, 160, 255), 1)
        cv2.putText(out, d.cls_name, (x1, max(8, y1 - 2)), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (10, 10, 220), 1, cv2.LINE_AA)

    y = 16
    for t in reconstructed_lines:
        cv2.putText(out, t[:120], (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 120, 0), 1, cv2.LINE_AA)
        y += 16
    if parsed_text:
        cv2.putText(out, f"parsed: {parsed_text[:100]}", (8, y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 0, 120), 1, cv2.LINE_AA)
    return out


def extract_room_dimensions(
    image: np.ndarray,
    room_polygon: Polygon,
    model_path: str,
    conf: float = 0.25,
    imgsz: int = 1024,
    device: str = "cpu",
    crop_pad: int = 30,
    crop_upscale: float = 2.0,
    tile_size: Optional[int] = None,
    debug: bool = False,
    debug_path: Optional[str] = None,
) -> RoomDimensionResult:
    """Primary per-room dimension extraction from character detections."""
    crop, _ = _extract_masked_room_crop(image, room_polygon, pad=crop_pad, upscale=crop_upscale)
    dets = detect_chars(crop, model_path=model_path, conf=conf, imgsz=imgsz, device=device, tile_size=tile_size)

    lines = group_into_lines(dets)
    candidates = merge_lines_to_candidates(lines)

    best_parsed: Optional[ParsedDimension] = None
    best_conf = 0.0
    for text, c in candidates:
        parsed = parse_dimension_candidate(text, char_conf=c)
        if parsed is None:
            continue
        if parsed.dimension_confidence > best_conf:
            best_conf = parsed.dimension_confidence
            best_parsed = parsed

    line_texts = [line_to_text(line)[0] for line in lines]

    if debug and debug_path:
        debug_img = draw_debug_chars(
            crop,
            dets,
            reconstructed_lines=line_texts,
            parsed_text=best_parsed.canonical_text if best_parsed else None,
        )
        Path(debug_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_path), debug_img)

    if best_parsed is None:
        return RoomDimensionResult(
            dimensions_text=None,
            parsed=None,
            confidence=0.0,
            source="char_detector",
            candidates=candidates,
        )

    return RoomDimensionResult(
        dimensions_text=best_parsed.canonical_text,
        parsed=best_parsed,
        confidence=best_parsed.dimension_confidence,
        source="char_detector",
        candidates=candidates,
    )


def assign_global_dimension_candidates_to_rooms(
    image: np.ndarray,
    room_polygons: Sequence[Polygon],
    model_path: str,
    conf: float = 0.25,
    imgsz: int = 1024,
    device: str = "cpu",
    tile_size: Optional[int] = 1024,
    max_distance_px: float = 120.0,
) -> Dict[int, ParsedDimension]:
    """Optional fallback: detect dimensions globally and attach to nearest room."""
    dets = detect_chars(image, model_path=model_path, conf=conf, imgsz=imgsz, device=device, tile_size=tile_size)
    lines = group_into_lines(dets)

    output: Dict[int, ParsedDimension] = {}
    for line in lines:
        text, c = line_to_text(line)
        parsed = parse_dimension_candidate(text, char_conf=c)
        if parsed is None:
            continue

        x1 = min(d.bbox_xyxy[0] for d in line)
        y1 = min(d.bbox_xyxy[1] for d in line)
        x2 = max(d.bbox_xyxy[2] for d in line)
        y2 = max(d.bbox_xyxy[3] for d in line)
        line_poly = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
        center = Point((x1 + x2) / 2.0, (y1 + y2) / 2.0)

        best_idx = -1
        best_score = -1.0
        for idx, rp in enumerate(room_polygons):
            inter = line_poly.intersection(rp).area
            ratio = inter / max(1.0, line_poly.area)
            dist = rp.distance(center)
            score = ratio - (dist / max_distance_px) * 0.15
            if ratio > 0.0 and score > best_score:
                best_score = score
                best_idx = idx
            elif ratio == 0.0 and dist <= max_distance_px and score > best_score:
                best_score = score
                best_idx = idx

        if best_idx >= 0 and (best_score > -0.1):
            if best_idx not in output or parsed.dimension_confidence > output[best_idx].dimension_confidence:
                output[best_idx] = parsed

    return output
