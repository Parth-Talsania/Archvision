"""End-to-end accuracy of the ArchVision pipeline against hand-checked ground truth.

Runs the same pipeline and settings as the web app (backend/services/
pipeline_service.py) on the plans listed in eval/ground_truth.txt and reports:

  - room recall / precision  (did we find each real room, and are detections real rooms)
  - label accuracy           (on matched rooms)
  - dimension accuracy       (exact, i.e. within 1/2", and within 3")
  - area error               (vs. area computed from the printed dimensions)

Matching: each ground-truth room is paired one-to-one with a predicted room
using the Hungarian algorithm. A pair is only allowed if the labels agree or
the dimensions agree to within 6"; dimension closeness is preferred, so two
"Toilet" rooms are told apart by their sizes.

Usage:
    python eval/evaluate.py              # run the pipeline (cached in eval/predictions/)
    python eval/evaluate.py --rerun      # ignore the cache
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import List, Optional, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
PLANS_DIR = EVAL_DIR / "plans"
PRED_DIR = EVAL_DIR / "predictions"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MATCH_DIM_TOL_IN = 6.0
INCHES_PER_METRE = 39.3701


# --------------------------------------------------------------------------
# Ground truth
# --------------------------------------------------------------------------

@dataclass
class GTRoom:
    label: str
    dims_raw: str
    dims_in: Optional[Tuple[float, float]]  # (width, height) in inches


@dataclass
class Plan:
    image: str
    rooms: List[GTRoom] = field(default_factory=list)


_FT_IN = re.compile(r"(\d+)\s*'\s*-?\s*(\d+)?\s*(?:(\d)\s*/\s*(\d))?\s*\"?")


def _parse_ft_in(text: str) -> Optional[float]:
    m = _FT_IN.search(text)
    if not m:
        return None
    ft, inch = int(m.group(1)), int(m.group(2) or 0)
    frac = int(m.group(3)) / int(m.group(4)) if m.group(3) else 0.0
    return ft * 12 + inch + frac


def parse_gt_dims(raw: str) -> Optional[Tuple[float, float]]:
    raw = raw.strip()
    if raw in ("", "-"):
        return None
    if raw.startswith("m:"):
        a, b = (float(v) for v in raw[2:].split("x"))
        return a * INCHES_PER_METRE, b * INCHES_PER_METRE
    left, right = raw.split(" x ")
    w, h = _parse_ft_in(left), _parse_ft_in(right)
    return (w, h) if w is not None and h is not None else None


def load_ground_truth(path: Path) -> List[Plan]:
    plans: List[Plan] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("=="):
            plans.append(Plan(image=line[2:].strip()))
            continue
        label, dims = (part.strip() for part in line.split("|", 1))
        plans[-1].rooms.append(GTRoom(label, dims, parse_gt_dims(dims)))
    return plans


# --------------------------------------------------------------------------
# Labels
# --------------------------------------------------------------------------

def canonical_label(label: Optional[str]) -> str:
    """Map label variants to one name: "Bed Room"/"Bedroom", "Sit-Out"/"Sit Out",
    "HALL & Dining"/"Hall", "Pooja room"/"Pooja", "Toilet"/"Bath"..."""
    s = re.sub(r"[^a-z]", "", (label or "").lower())
    if "master" in s:
        return "master bedroom"
    if "bed" in s:
        return "bedroom"
    if any(k in s for k in ("toilet", "bath", "wc")):
        return "toilet"
    if "kitchen" in s:
        return "kitchen"
    if "hall" in s:
        return "hall"
    if "living" in s or "drawing" in s:
        return "living"
    if "dining" in s:
        return "dining"
    if "pooja" in s or "puja" in s:
        return "pooja"
    if "sitout" in s:
        return "sit out"
    if "service" in s or "utility" in s:
        return "service"
    if "balcony" in s:
        return "balcony"
    return s or "room"


# --------------------------------------------------------------------------
# Predictions
# --------------------------------------------------------------------------

def predict(image_path: Path, rerun: bool) -> List[dict]:
    cache = PRED_DIR / f"{image_path.stem}.json"
    if cache.exists() and not rerun:
        return json.loads(cache.read_text(encoding="utf-8"))

    import cv2
    from backend.services.pipeline_service import _get_pipeline
    from pipeline.frontend_schema import build_frontend_output

    pipe = _get_pipeline()
    pipe.analyze_path(str(image_path))
    img = cv2.imread(str(image_path))
    out = build_frontend_output(
        image_path=str(image_path), image_width=img.shape[1], image_height=img.shape[0],
        rooms=pipe.last_rooms, source_type="image",
    )
    rooms = [
        {
            "label": r.get("label"),
            "dimensions": r.get("dimensions"),
            "dimensions_parsed": r.get("dimensions_parsed"),
            "area_sqft": (r.get("area") or {}).get("value_sqft"),
        }
        for r in out["pages"][0]["rooms"]
    ]
    PRED_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(rooms, indent=2), encoding="utf-8")
    return rooms


def pred_dims_in(room: dict) -> Optional[Tuple[float, float]]:
    dp = room.get("dimensions_parsed") or {}
    if dp.get("width_ft") is None or dp.get("height_ft") is None:
        return None
    return dp["width_ft"] * 12 + (dp.get("width_in") or 0), dp["height_ft"] * 12 + (dp.get("height_in") or 0)


def dim_error(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Largest side error in inches, allowing width/height to be swapped."""
    straight = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    swapped = max(abs(a[0] - b[1]), abs(a[1] - b[0]))
    return min(straight, swapped)


# --------------------------------------------------------------------------
# Matching and scoring
# --------------------------------------------------------------------------

@dataclass
class Match:
    gt: GTRoom
    pred: Optional[dict]
    label_ok: bool = False
    dim_err: Optional[float] = None  # None = not comparable
    area_err_pct: Optional[float] = None


def match_plan(gt_rooms: List[GTRoom], preds: List[dict]) -> List[Match]:
    big = 1e6
    cost = np.full((len(gt_rooms), max(len(preds), 1)), big)
    for i, g in enumerate(gt_rooms):
        for j, p in enumerate(preds):
            label_ok = canonical_label(g.label) == canonical_label(p.get("label"))
            pd = pred_dims_in(p)
            err = dim_error(g.dims_in, pd) if g.dims_in and pd else None
            if not label_ok and (err is None or err > MATCH_DIM_TOL_IN):
                continue
            cost[i, j] = (err if err is not None else 60.0) + (0.0 if label_ok else 30.0)
    rows, cols = linear_sum_assignment(cost)
    assigned = {r: c for r, c in zip(rows, cols) if cost[r, c] < big}

    matches = []
    for i, g in enumerate(gt_rooms):
        if i not in assigned:
            matches.append(Match(g, None))
            continue
        p = preds[assigned[i]]
        m = Match(g, p, label_ok=canonical_label(g.label) == canonical_label(p.get("label")))
        pd = pred_dims_in(p)
        if g.dims_in and pd:
            m.dim_err = dim_error(g.dims_in, pd)
        if g.dims_in and p.get("area_sqft"):
            gt_area = g.dims_in[0] * g.dims_in[1] / 144.0
            m.area_err_pct = abs(p["area_sqft"] - gt_area) / gt_area * 100
        matches.append(m)
    return matches


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "–"


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate the pipeline against eval/ground_truth.txt")
    ap.add_argument("--rerun", action="store_true", help="Re-run the pipeline instead of using cached predictions")
    args = ap.parse_args()

    plans = load_ground_truth(EVAL_DIR / "ground_truth.txt")
    rows, all_matches, total_pred = [], [], 0
    for plan in plans:
        preds = predict(PLANS_DIR / plan.image, args.rerun)
        matches = match_plan(plan.rooms, preds)
        all_matches.extend(matches)
        total_pred += len(preds)
        found = [m for m in matches if m.pred]
        dimmed = [m for m in found if m.gt.dims_in]
        rows.append((plan.image, len(plan.rooms), len(preds), len(found),
                     sum(m.label_ok for m in found),
                     sum(1 for m in dimmed if m.dim_err is not None and m.dim_err <= 0.5), len(dimmed)))

    found = [m for m in all_matches if m.pred]
    gt_with_dims = [m for m in found if m.gt.dims_in]
    exact = sum(1 for m in gt_with_dims if m.dim_err is not None and m.dim_err <= 0.5)
    within3 = sum(1 for m in gt_with_dims if m.dim_err is not None and m.dim_err <= 3)
    area_errs = [m.area_err_pct for m in found if m.area_err_pct is not None]
    n_gt = len(all_matches)

    lines = [
        "# End-to-end evaluation",
        "",
        f"{len(plans)} floor plans ({n_gt} rooms) that the model never saw during training or validation.",
        "Ground truth: room labels and dimensions as printed on each plan (`eval/ground_truth.txt`).",
        "Reproduce with `python eval/evaluate.py`.",
        "",
        "Note: one dimension-parser fix (OCR reading a dash as a dot, and a missing space after",
        "\"x\") was made after seeing plan E-22 fail in this evaluation, so these plans are not",
        "fully untouched test data. Without that fix, exact dimensions were 53/67 instead of 54/68.",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Rooms found (recall) | {pct(len(found), n_gt)} |",
        f"| Detections that are real rooms (precision) | {pct(len(found), total_pred)} |",
        f"| Correct label, of rooms found | {pct(sum(m.label_ok for m in found), len(found))} |",
        f"| Dimensions exact (within ½\"), of rooms found | {pct(exact, len(gt_with_dims))} |",
        f"| Dimensions within 3\", of rooms found | {pct(within3, len(gt_with_dims))} |",
        f"| Median area error, where area was computed | {median(area_errs):.1f}% (mean {mean(area_errs):.1f}%, n={len(area_errs)}) |" if area_errs else "| Median area error | – |",
        "",
        "## Per plan",
        "",
        "| Plan | Rooms | Detections | Found | Label correct | Dims exact |",
        "|---|---|---|---|---|---|",
    ]
    for image, n, npred, nf, nl, nd, ndd in rows:
        lines.append(f"| {image} | {n} | {npred} | {nf} | {nl}/{nf} | {nd}/{ndd} |")

    lines += ["", "## Misses and errors", "", "| Plan | Ground truth | Prediction | Problem |", "|---|---|---|---|"]
    for plan in plans:
        for m in match_plan(plan.rooms, predict(PLANS_DIR / plan.image, False)):
            gt = f"{m.gt.label} · {m.gt.dims_raw}"
            if m.pred is None:
                lines.append(f"| {plan.image} | {gt} | – | not found |")
                continue
            problems = []
            if not m.label_ok:
                problems.append("label")
            if m.gt.dims_in and (m.dim_err is None or m.dim_err > 0.5):
                problems.append("no dimensions" if m.dim_err is None else f"dims off by {m.dim_err:.1f}\"")
            if problems:
                pred = f"{m.pred.get('label')} · {m.pred.get('dimensions') or '-'}"
                lines.append(f"| {plan.image} | {gt} | {pred} | {', '.join(problems)} |")

    lines += [
        "",
        "## Experiments",
        "",
        "**2x upscaling before analysis** (for small, low-resolution plans): rooms found 69 -> 71,",
        "exact dimensions 54/68 -> 57/70. It helped the two low-resolution plans (N2 1 -> 4, S15 3 -> 5)",
        "but made E-22, N18 and W8 one room worse each, and processes 4x the pixels. Not adopted: the",
        "net gain is within noise on 10 plans, and picking it from these same plans would be tuning",
        "on the test set. Better OCR on low-resolution scans needs a stronger OCR model or",
        "higher-resolution source images.",
    ]

    report = "\n".join(lines) + "\n"
    (EVAL_DIR / "RESULTS.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
