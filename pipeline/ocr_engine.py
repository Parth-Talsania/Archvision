from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import easyocr
import numpy as np

from .config import OCRConfig
from .geometry import CropTransform, box_polygon
from .types import OCRToken

LOGGER = logging.getLogger(__name__)
_READER_CACHE: Dict[Tuple[Tuple[str, ...], bool], easyocr.Reader] = {}


def get_easyocr_reader(languages: Tuple[str, ...], gpu: bool) -> easyocr.Reader:
    key = (languages, gpu)
    if key not in _READER_CACHE:
        model_dir = Path("results/easyocr_cache/model")
        user_dir = Path("results/easyocr_cache/user")
        model_dir.mkdir(parents=True, exist_ok=True)
        user_dir.mkdir(parents=True, exist_ok=True)
        _READER_CACHE[key] = easyocr.Reader(
            list(languages),
            gpu=gpu,
            model_storage_directory=str(model_dir),
            user_network_directory=str(user_dir),
        )
    return _READER_CACHE[key]


# ---------------------------------------------------------------------------
# Preprocessing: keep it minimal.  The old pipeline applied CLAHE, median
# blur, and adaptive threshold which destroyed thin strokes (',",-, fractions).
# New approach: grayscale + gentle resize only.
# ---------------------------------------------------------------------------

def preprocess_for_ocr(crop_img: np.ndarray, config: OCRConfig) -> Tuple[np.ndarray, float]:
    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY) if crop_img.ndim == 3 else crop_img.copy()
    h, w = gray.shape[:2]
    max_dim = max(h, w)

    # Adaptive scale: large images stay as-is, small ones get upscaled
    if config.adaptive_scale:
        if max_dim >= 800:
            scale = 1.0
        elif max_dim >= 400:
            scale = min(2.0, float(config.upscale))
        else:
            scale = float(max(1, config.upscale))
    else:
        scale = float(max(1, config.upscale))

    if scale > 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    return gray, scale


def _run_easyocr_raw(reader: easyocr.Reader, image: np.ndarray,
                     allowlist: str, min_conf: float) -> List[Tuple]:
    return reader.readtext(
        image, detail=1, paragraph=False, allowlist=allowlist,
    )


class OCREngine:
    def __init__(self, config: OCRConfig, languages: Optional[List[str]] = None):
        self.config = config
        self.languages = tuple(languages or ["en"])
        self.reader = get_easyocr_reader(self.languages, config.gpu)

    # ------------------------------------------------------------------
    # Core: multi-scale OCR on a single image.
    # Run at two scales to cover both large and small text. Deduplicate.
    # ------------------------------------------------------------------
    def run_easyocr(self, image: np.ndarray) -> List[OCRToken]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
        h, w = gray.shape[:2]
        max_dim = max(h, w)

        scales = self._pick_scales(max_dim)
        all_tokens: List[OCRToken] = []
        for sc in scales:
            if sc == 1.0:
                img = gray
            else:
                img = cv2.resize(gray, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
            toks = self._ocr_at_scale(img, sc)
            all_tokens.extend(toks)

        return self._dedupe(all_tokens)

    def _pick_scales(self, max_dim: int) -> List[float]:
        if max_dim >= 800:
            return [1.0]
        if max_dim >= 400:
            return [1.0, 2.0]
        return [2.0, 3.0]

    def _ocr_at_scale(self, gray_scaled: np.ndarray, scale: float) -> List[OCRToken]:
        results = self.reader.readtext(
            gray_scaled, detail=1, paragraph=False,
            allowlist=self.config.allowlist,
        )
        tokens: List[OCRToken] = []
        min_ar, max_ar = self.config.line_aspect_ratio_reject
        for box, text, conf in results:
            if text is None:
                continue
            text = str(text).strip()
            if not text:
                continue
            if conf < self.config.min_conf_keep:
                continue
            pts = np.asarray(box, dtype=np.float32) / scale
            xs, ys = pts[:, 0], pts[:, 1]
            x1, x2 = float(xs.min()), float(xs.max())
            y1, y2 = float(ys.min()), float(ys.max())
            bw, bh = max(1e-3, x2 - x1), max(1e-3, y2 - y1)
            aspect = bw / bh
            if aspect < min_ar or aspect > max_ar:
                continue
            points = [(float(p[0]), float(p[1])) for p in pts]
            poly = box_polygon(points)
            if poly.is_empty:
                continue
            tokens.append(OCRToken(
                text=text, conf=float(conf), box=points,
                box_poly=poly, box_bbox=(x1, y1, x2, y2),
                source="easyocr", meta={"scale": scale},
            ))
        return tokens

    # ------------------------------------------------------------------
    # Deduplication: drop spatially overlapping tokens, keep highest conf.
    # Uses *minimum area* as denominator so a small box inside a big box
    # is still caught.
    # ------------------------------------------------------------------
    def _dedupe(self, tokens: List[OCRToken]) -> List[OCRToken]:
        kept: List[OCRToken] = []
        for tok in sorted(tokens, key=lambda t: t.conf, reverse=True):
            dup = False
            for old in kept:
                inter = tok.box_poly.intersection(old.box_poly).area
                if inter <= 0:
                    continue
                denom = max(1e-6, min(tok.box_poly.area, old.box_poly.area))
                ratio = inter / denom
                if ratio >= 0.5:
                    dup = True
                    break
            if not dup:
                kept.append(tok)
        return kept

    @staticmethod
    def to_global(tokens: List[OCRToken], transform: CropTransform) -> List[OCRToken]:
        out: List[OCRToken] = []
        for t in tokens:
            gpts = [transform.to_global(x, y) for x, y in t.box]
            gpoly = box_polygon(gpts)
            minx, miny, maxx, maxy = gpoly.bounds
            out.append(OCRToken(
                text=t.text, conf=t.conf,
                box=[(float(x), float(y)) for x, y in gpts],
                box_poly=gpoly,
                box_bbox=(float(minx), float(miny), float(maxx), float(maxy)),
                source=t.source, meta=dict(t.meta or {}),
            ))
        return out
