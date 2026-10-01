from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import cv2
import numpy as np


ROOM_KEYWORDS = {
    "bedroom",
    "master bedroom",
    "bath",
    "bathroom",
    "toilet",
    "wc",
    "kitchen",
    "living",
    "dining",
    "foyer",
    "utility",
    "wardrobe",
    "corridor",
    "lobby",
    "study",
    "maid",
    "terrace",
    "balcony",
    "hall",
    "powder",
}

PLAN_CONTEXT_KEYWORDS = {
    "floor plan",
    "typical floor",
    "penthouse",
    "level",
    "sq ft",
    "sqft",
    "sqm",
    "unit",
    "type",
    "layout",
}

NEGATIVE_KEYWORDS = {
    "concierge",
    "luxury",
    "facilities",
    "specifications",
    "address",
    "neighbourhood",
    "brochure",
    "brand",
    "hotel",
    "lifestyle",
    "spa",
    "restaurant",
    "service",
    "ritz",
    "map",
}


@dataclass
class TextScore:
    room_hits: int
    context_hits: int
    neg_hits: int
    score: float


@dataclass
class ImageFeatures:
    edge_ratio: float
    line_count: int
    orthogonal_ratio: float
    colorfulness: float
    image_score: float


def normalize_text(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def count_keyword_hits(norm_text: str, keywords: set[str]) -> int:
    if not norm_text:
        return 0
    hits = 0
    for k in keywords:
        hits += norm_text.count(k)
    return hits


def score_text(raw_text: str) -> TextScore:
    norm = normalize_text(raw_text)
    room_hits = count_keyword_hits(norm, ROOM_KEYWORDS)
    context_hits = count_keyword_hits(norm, PLAN_CONTEXT_KEYWORDS)
    neg_hits = count_keyword_hits(norm, NEGATIVE_KEYWORDS)
    score = (room_hits * 0.10 + context_hits * 0.05) - (neg_hits * 0.03)
    if room_hits >= 8:
        score += 0.10
    score = float(np.clip(score, 0.0, 1.0))
    return TextScore(room_hits=room_hits, context_hits=context_hits, neg_hits=neg_hits, score=score)


def normalize_range(x: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return float(np.clip((x - low) / (high - low), 0.0, 1.0))


def colorfulness_metric(img_bgr: np.ndarray) -> float:
    b, g, r = cv2.split(img_bgr.astype(np.float32))
    rg = np.abs(r - g)
    yb = np.abs(0.5 * (r + g) - b)
    return float(np.sqrt(np.std(rg) ** 2 + np.std(yb) ** 2) + 0.3 * np.sqrt(np.mean(rg) ** 2 + np.mean(yb) ** 2))


def edge_line_features(img_bgr: np.ndarray) -> Tuple[float, int, float]:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_ratio = float(np.count_nonzero(edges)) / float(edges.size)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180.0, threshold=80, minLineLength=max(20, int(min(img_bgr.shape[:2]) * 0.06)), maxLineGap=8)
    if lines is None:
        return edge_ratio, 0, 0.0
    angles = []
    for l in lines[:, 0, :]:
        x1, y1, x2, y2 = l
        angle = np.degrees(np.arctan2((y2 - y1), (x2 - x1)))
        angle = abs(angle) % 180.0
        if angle > 90:
            angle = 180 - angle
        angles.append(angle)
    if not angles:
        return edge_ratio, 0, 0.0
    angles_arr = np.asarray(angles, dtype=np.float32)
    orth = np.logical_or(np.abs(angles_arr - 0) <= 12, np.abs(angles_arr - 90) <= 12)
    orth_ratio = float(np.count_nonzero(orth)) / float(len(angles_arr))
    return edge_ratio, int(len(angles_arr)), orth_ratio


def score_image_thumbnail(img_bgr: np.ndarray) -> ImageFeatures:
    edge_ratio, line_count, orthogonal_ratio = edge_line_features(img_bgr)
    colorfulness = colorfulness_metric(img_bgr)

    edge_n = normalize_range(edge_ratio, 0.02, 0.12)
    orth_n = normalize_range(orthogonal_ratio, 0.30, 0.80)
    color_n = normalize_range(colorfulness, 10.0, 60.0)
    image_score = float(np.clip(0.45 * edge_n + 0.35 * orth_n - 0.20 * color_n, 0.0, 1.0))
    return ImageFeatures(
        edge_ratio=edge_ratio,
        line_count=line_count,
        orthogonal_ratio=orthogonal_ratio,
        colorfulness=colorfulness,
        image_score=image_score,
    )

