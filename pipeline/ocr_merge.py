from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median
from typing import Dict, List, Tuple

from .types import OCRToken


@dataclass
class OCRMergeResult:
    ocr_lines: List[str]
    merged_text: str
    line_tokens: List[List[OCRToken]]


# Watermark patterns common on Indian floor plan sites
_WATERMARK_RE = re.compile(
    r'(?:www\.|\.(com|in|org|net)\b|https?://|indianfloorplan|floorplans?\.|naksha)',
    re.IGNORECASE,
)


def filter_watermark_tokens(tokens: List[OCRToken]) -> List[OCRToken]:
    return [t for t in tokens if t.text.strip() and not _WATERMARK_RE.search(t.text)]


def group_tokens_into_lines(tokens: List[OCRToken]) -> List[List[OCRToken]]:
    if not tokens:
        return []
    # PDF-native tokens have block/line metadata
    if all(("block_no" in t.meta and "line_no" in t.meta) for t in tokens):
        groups: Dict[Tuple[int, int], List[OCRToken]] = {}
        for t in tokens:
            key = (int(t.meta.get("block_no", 0)), int(t.meta.get("line_no", 0)))
            groups.setdefault(key, []).append(t)
        ordered = sorted(
            groups.values(),
            key=lambda g: (
                sum((x.box_bbox[1] + x.box_bbox[3]) / 2.0 for x in g) / max(1, len(g)),
                min(x.box_bbox[0] for x in g),
            ),
        )
        return [sorted(g, key=lambda t: t.box_bbox[0]) for g in ordered]

    heights = [max(1e-3, t.box_bbox[3] - t.box_bbox[1]) for t in tokens]
    med_h = float(median(heights))
    sorted_tokens = sorted(tokens, key=lambda t: ((t.box_bbox[1] + t.box_bbox[3]) / 2.0, t.box_bbox[0]))

    lines: List[Dict] = []
    for token in sorted_tokens:
        yc = (token.box_bbox[1] + token.box_bbox[3]) / 2.0
        matched = False
        for line in lines:
            if abs(yc - line["yc"]) < 0.5 * med_h:
                line["tokens"].append(token)
                vals = [(t.box_bbox[1] + t.box_bbox[3]) / 2.0 for t in line["tokens"]]
                line["yc"] = sum(vals) / len(vals)
                matched = True
                break
        if not matched:
            lines.append({"yc": yc, "tokens": [token]})

    return [
        sorted(line["tokens"], key=lambda t: t.box_bbox[0])
        for line in sorted(lines, key=lambda r: r["yc"])
    ]


def _should_glue(prev: str, nxt: str) -> bool:
    prev, nxt = prev.strip(), nxt.strip()
    if not prev or not nxt:
        return False
    if prev in {"x", "X", "-", "'", '"'} or nxt in {"x", "X", "-", "'", '"'}:
        return True
    if prev.endswith("'") and re.match(r"^-?\d+\"?$", nxt):
        return True
    if prev.endswith("-") and re.match(r"^\d+\"?$", nxt):
        return True
    if re.match(r"^\d+'?$", prev) and re.match(r"^-?\d+\"?$", nxt):
        return True
    return False


def _join_line_tokens(tokens: List[OCRToken], med_h: float) -> str:
    if not tokens:
        return ""
    parts = [tokens[0].text.strip()]
    for left, right in zip(tokens[:-1], tokens[1:]):
        gap = right.box_bbox[0] - left.box_bbox[2]
        raw = right.text.strip()
        if gap < 0.2 * med_h or _should_glue(parts[-1], raw):
            parts[-1] = f"{parts[-1]}{raw}"
        else:
            parts.append(raw)
    return " ".join(p for p in parts if p)


def merge_room_tokens(tokens: List[OCRToken]) -> OCRMergeResult:
    if not tokens:
        return OCRMergeResult(ocr_lines=[], merged_text="", line_tokens=[])
    heights = [max(1e-3, t.box_bbox[3] - t.box_bbox[1]) for t in tokens]
    med_h = float(median(heights))
    line_groups = group_tokens_into_lines(tokens)
    lines = [_join_line_tokens(grp, med_h) for grp in line_groups]
    lines = [l for l in lines if l.strip()]
    return OCRMergeResult(
        ocr_lines=lines, merged_text="\n".join(lines), line_tokens=line_groups,
    )
