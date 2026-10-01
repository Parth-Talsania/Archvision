from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from .geometry import box_polygon
from .types import OCRToken

LOGGER = logging.getLogger(__name__)
_PADDLE_CACHE: Dict[Tuple[str, bool], object] = {}
_paddle_cls = None
_paddle_import_attempted = False
_paddle_broken = False  # Set True if runtime fails, skip all future calls


def _get_paddle_cls():
    """Lazy import PaddleOCR so it works even if installed after first import."""
    global _paddle_cls, _paddle_import_attempted
    if _paddle_import_attempted:
        return _paddle_cls
    _paddle_import_attempted = True
    try:
        from paddleocr import PaddleOCR  # type: ignore
        _paddle_cls = PaddleOCR
    except Exception as exc:
        LOGGER.warning("PaddleOCR import failed: %s", repr(exc))
        _paddle_cls = None
    return _paddle_cls


def get_paddle_reader(lang: str = "en", use_gpu: bool = False) -> Optional[object]:
    PaddleOCR = _get_paddle_cls()
    if PaddleOCR is None:
        return None
    key = (lang, use_gpu)
    if key not in _PADDLE_CACHE:
        try:
            # Try v2.x API first
            _PADDLE_CACHE[key] = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False, use_gpu=use_gpu)
        except (TypeError, ValueError):
            try:
                # PaddleOCR v3.4+ uses different params
                _PADDLE_CACHE[key] = PaddleOCR(lang=lang)
            except Exception as exc:
                LOGGER.warning("PaddleOCR init failed: %s", repr(exc))
                return None
    return _PADDLE_CACHE[key]


def run_paddleocr(image_bgr: np.ndarray, use_gpu: bool = False, min_conf: float = 0.2) -> List[OCRToken]:
    global _paddle_broken
    if _paddle_broken:
        return []

    reader = get_paddle_reader(lang="en", use_gpu=use_gpu)
    if reader is None:
        return []

    # Try v2 API (ocr method) first, then v3 API (predict method)
    raw_lines = None
    try:
        result = reader.ocr(image_bgr, cls=True)  # type: ignore[attr-defined]
        if result:
            raw_lines = result[0] if isinstance(result, list) else result
    except (AttributeError, Exception) as exc:
        LOGGER.debug("PaddleOCR v2 ocr() failed: %s, trying predict()", repr(exc))
        try:
            results = list(reader.predict(image_bgr))  # type: ignore[attr-defined]
            if results and hasattr(results[0], 'rec_texts'):
                r = results[0]
                raw_lines = []
                for i, (poly, txt, score) in enumerate(zip(r.dt_polys, r.rec_texts, r.rec_scores)):
                    raw_lines.append([poly.tolist(), (txt, float(score))])
        except Exception as exc2:
            LOGGER.warning("PaddleOCR runtime error, disabling for this session: %s", repr(exc2))
            _paddle_broken = True
            return []

    tokens: List[OCRToken] = []
    if not raw_lines:
        return tokens
    for li, item in enumerate(raw_lines):
        if not item or len(item) < 2:
            continue
        quad = item[0]
        txt, conf = item[1][0], float(item[1][1])
        if conf < min_conf:
            continue
        pts = [(float(p[0]), float(p[1])) for p in quad]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        box = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        poly = box_polygon(box)
        if poly.is_empty:
            continue
        tokens.append(
            OCRToken(
                text=str(txt).strip(),
                conf=conf,
                box=box,
                box_poly=poly,
                box_bbox=(x1, y1, x2, y2),
                source="paddleocr",
                meta={"line_idx": li},
            )
        )
    return tokens
