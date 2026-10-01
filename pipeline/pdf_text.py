from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import fitz
import numpy as np

from .geometry import box_polygon
from .types import OCRToken

_DOC_CACHE: Dict[str, fitz.Document] = {}


def _get_doc(pdf_path: str) -> fitz.Document:
    key = str(Path(pdf_path))
    if key not in _DOC_CACHE:
        _DOC_CACHE[key] = fitz.open(key)
    return _DOC_CACHE[key]


def _bbox_intersects(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)


def _normalize_token_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("×", "x")
    t = re.sub(r"\s+", " ", t)
    return t


def extract_pdf_tokens_for_crop(
    pdf_path: str,
    page_number: int,
    crop_bbox_px_page: Tuple[float, float, float, float],
    render_dpi: int,
    rotation_handling: str = "auto",
) -> List[OCRToken]:
    """
    Extract PDF-native word tokens in crop coordinate frame.
    """
    _ = rotation_handling  # kept for API compatibility
    doc = _get_doc(pdf_path)
    page = doc[int(page_number) - 1]
    scale = float(render_dpi) / 72.0

    words: List[Tuple] = []
    try:
        textpage = page.get_textpage(matrix=fitz.Matrix(scale, scale))
        words = list(textpage.extractWORDS())
    except Exception:
        words = list(page.get_text("words"))
        # Fallback returns page-point coordinates; scale to page-pixel coords.
        words = [
            (w[0] * scale, w[1] * scale, w[2] * scale, w[3] * scale, *w[4:])
            for w in words
        ]

    cx1, cy1, cx2, cy2 = crop_bbox_px_page
    crop_bbox = (float(cx1), float(cy1), float(cx2), float(cy2))
    tokens: List[OCRToken] = []
    for w in words:
        if len(w) < 5:
            continue
        x0, y0, x1, y1 = float(w[0]), float(w[1]), float(w[2]), float(w[3])
        txt = _normalize_token_text(str(w[4]))
        if not txt:
            continue
        if len(txt) == 1 and (not txt.isalnum()) and txt not in {"'", '"', "-", "x", "X"}:
            continue
        if not _bbox_intersects((x0, y0, x1, y1), crop_bbox):
            continue
        lx0, ly0, lx1, ly1 = x0 - cx1, y0 - cy1, x1 - cx1, y1 - cy1
        box = [(lx0, ly0), (lx1, ly0), (lx1, ly1), (lx0, ly1)]
        poly = box_polygon(box)
        if poly.is_empty:
            continue
        meta = {}
        if len(w) >= 8:
            meta = {"block_no": int(w[5]), "line_no": int(w[6]), "word_no": int(w[7])}
        tokens.append(
            OCRToken(
                text=txt,
                conf=1.0,
                box=[(float(x), float(y)) for x, y in box],
                box_poly=poly,
                box_bbox=(float(lx0), float(ly0), float(lx1), float(ly1)),
                source="pdf_text",
                meta=meta,
            )
        )
    return tokens


def render_pdf_crop(
    pdf_path: str,
    page_number: int,
    bbox_pdf_points: Tuple[float, float, float, float],
    dpi: int,
) -> np.ndarray:
    """
    Render a PDF crop directly from page points at target DPI.
    """
    doc = _get_doc(pdf_path)
    page = doc[int(page_number) - 1]
    rect = fitz.Rect(*bbox_pdf_points)
    scale = float(dpi) / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False)
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def save_pdf_text_debug_overlay(
    pdf_path: str,
    page_number: int,
    render_dpi: int,
    out_path: str,
) -> None:
    """
    Render full page and overlay all PDF words to validate coordinate alignment.
    """
    doc = _get_doc(pdf_path)
    page = doc[int(page_number) - 1]
    scale = float(render_dpi) / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    try:
        textpage = page.get_textpage(matrix=fitz.Matrix(scale, scale))
        words = list(textpage.extractWORDS())
    except Exception:
        words = list(page.get_text("words"))
        words = [(w[0] * scale, w[1] * scale, w[2] * scale, w[3] * scale, *w[4:]) for w in words]
    for w in words:
        if len(w) < 5:
            continue
        x0, y0, x1, y1 = int(w[0]), int(w[1]), int(w[2]), int(w[3])
        txt = str(w[4])[:24]
        cv2.rectangle(bgr, (x0, y0), (x1, y1), (0, 255, 255), 1)
        cv2.putText(bgr, txt, (x0, max(12, y0 - 2)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1, cv2.LINE_AA)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), bgr)

