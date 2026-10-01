from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np

from .features import colorfulness_metric, edge_line_features, normalize_range


@dataclass
class RegionCandidate:
    x1: int
    y1: int
    x2: int
    y2: int
    area_ratio: float
    edge_density: float
    crop_score: float = 0.0


def _iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw = max(0, ix2 - ix1 + 1)
    ih = max(0, iy2 - iy1 + 1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    aa = max(1, (ax2 - ax1 + 1) * (ay2 - ay1 + 1))
    ba = max(1, (bx2 - bx1 + 1) * (by2 - by1 + 1))
    return float(inter) / float(aa + ba - inter)


def _close_or_overlap(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int], dist_thresh: int = 30) -> bool:
    if _iou(a, b) > 0.10:
        return True
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    dx = max(0, max(bx1 - ax2, ax1 - bx2))
    dy = max(0, max(by1 - ay2, ay1 - by2))
    return dx < dist_thresh and dy < dist_thresh


def merge_bboxes(bboxes: List[Tuple[int, int, int, int]], dist_thresh: int = 30) -> List[Tuple[int, int, int, int]]:
    changed = True
    out = bboxes[:]
    while changed and out:
        changed = False
        used = [False] * len(out)
        merged: List[Tuple[int, int, int, int]] = []
        for i, b in enumerate(out):
            if used[i]:
                continue
            x1, y1, x2, y2 = b
            used[i] = True
            for j in range(i + 1, len(out)):
                if used[j]:
                    continue
                if _close_or_overlap((x1, y1, x2, y2), out[j], dist_thresh=dist_thresh):
                    ox1, oy1, ox2, oy2 = out[j]
                    x1, y1 = min(x1, ox1), min(y1, oy1)
                    x2, y2 = max(x2, ox2), max(y2, oy2)
                    used[j] = True
                    changed = True
            merged.append((x1, y1, x2, y2))
        out = merged
    return out


def detect_candidate_regions(
    page_img_bgr: np.ndarray,
    min_region_area_ratio: float,
    max_regions_per_page: int,
) -> Tuple[List[RegionCandidate], np.ndarray]:
    h, w = page_img_bgr.shape[:2]
    page_area = float(h * w)
    gray = cv2.cvtColor(page_img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    dil = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)), iterations=2)
    closed = cv2.morphologyEx(dil, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25)), iterations=2)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats((closed > 0).astype(np.uint8), connectivity=8)

    bboxes: List[Tuple[int, int, int, int]] = []
    for lid in range(1, num_labels):
        x, y, ww, hh, area = stats[lid]
        if ww <= 0 or hh <= 0:
            continue
        area_ratio = (ww * hh) / page_area
        if area_ratio < min_region_area_ratio:
            continue
        wr = ww / float(w)
        hr = hh / float(h)
        if wr < 0.20 or hr < 0.20:
            continue
        x1, y1 = int(x), int(y)
        x2, y2 = int(x + ww - 1), int(y + hh - 1)
        roi_edges = edges[y1 : y2 + 1, x1 : x2 + 1]
        edge_density = float(np.count_nonzero(roi_edges)) / float(max(1, roi_edges.size))
        if edge_density < 0.02:
            continue
        bboxes.append((x1, y1, x2, y2))

    if not bboxes:
        # Fallback via dominant background suppression.
        small = cv2.resize(page_img_bgr, (max(32, w // 6), max(32, h // 6)), interpolation=cv2.INTER_AREA)
        flat = small.reshape(-1, 3).astype(np.float32)
        mean_bg = np.median(flat, axis=0)
        dist = np.linalg.norm(page_img_bgr.astype(np.float32) - mean_bg[None, None, :], axis=2)
        fg = (dist > 18).astype(np.uint8) * 255
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21)), iterations=2)
        n2, _, st2, _ = cv2.connectedComponentsWithStats((fg > 0).astype(np.uint8), connectivity=8)
        for lid in range(1, n2):
            x, y, ww, hh, area = st2[lid]
            if ww <= 0 or hh <= 0:
                continue
            area_ratio = (ww * hh) / page_area
            if area_ratio < min_region_area_ratio:
                continue
            wr = ww / float(w)
            hr = hh / float(h)
            if wr < 0.20 or hr < 0.20:
                continue
            bboxes.append((int(x), int(y), int(x + ww - 1), int(y + hh - 1)))

    bboxes = merge_bboxes(bboxes, dist_thresh=30)
    cands: List[RegionCandidate] = []
    for x1, y1, x2, y2 in bboxes:
        roi_edges = edges[y1 : y2 + 1, x1 : x2 + 1]
        edge_density = float(np.count_nonzero(roi_edges)) / float(max(1, roi_edges.size))
        ar = ((x2 - x1 + 1) * (y2 - y1 + 1)) / page_area
        cands.append(RegionCandidate(x1=x1, y1=y1, x2=x2, y2=y2, area_ratio=ar, edge_density=edge_density))

    cands.sort(key=lambda c: ((c.x2 - c.x1 + 1) * (c.y2 - c.y1 + 1)), reverse=True)
    return cands[:max_regions_per_page], edges


def score_crop(crop_bgr: np.ndarray) -> float:
    edge_ratio, _, orth_ratio = edge_line_features(crop_bgr)
    color = colorfulness_metric(crop_bgr)
    edge_n = normalize_range(edge_ratio, 0.02, 0.15)
    orth_n = normalize_range(orth_ratio, 0.30, 0.85)
    color_n = normalize_range(color, 10.0, 60.0)
    return float(np.clip(0.50 * edge_n + 0.35 * orth_n - 0.15 * color_n, 0.0, 1.0))


def pad_bbox(x1: int, y1: int, x2: int, y2: int, pad: int, w: int, h: int) -> Tuple[int, int, int, int]:
    return (
        max(0, x1 - pad),
        max(0, y1 - pad),
        min(w - 1, x2 + pad),
        min(h - 1, y2 + pad),
    )

