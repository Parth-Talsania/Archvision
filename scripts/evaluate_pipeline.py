from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional


def _safe_load_json(path: Path) -> Optional[Dict]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _fuzzy_contains(label: str, expected: str) -> bool:
    l = label.lower().strip()
    e = expected.lower().strip()
    return e in l or l in e


def evaluate_one(pred: Dict, exp: Dict) -> Dict:
    pred_rooms = pred.get("rooms", [])
    got_labels = [str(r.get("label") or r.get("name") or "").strip() for r in pred_rooms]
    dims_present = sum(1 for r in pred_rooms if r.get("dimension_parsed") or r.get("dimensions_text"))
    parse_rate = 0.0 if not pred_rooms else dims_present / len(pred_rooms)

    expected_labels = exp.get("expected_labels", [])
    label_hits = 0
    for e in expected_labels:
        if any(_fuzzy_contains(lbl, e) for lbl in got_labels):
            label_hits += 1
    label_hit_rate = 1.0 if not expected_labels else label_hits / len(expected_labels)

    min_rooms = exp.get("min_rooms")
    max_rooms = exp.get("max_rooms")
    room_count = len(pred_rooms)
    room_count_error = 0
    if min_rooms is not None and room_count < int(min_rooms):
        room_count_error = int(min_rooms) - room_count
    if max_rooms is not None and room_count > int(max_rooms):
        room_count_error = room_count - int(max_rooms)
    return {
        "room_count": room_count,
        "room_count_error": room_count_error,
        "label_hit_rate": round(label_hit_rate, 4),
        "dimension_parse_rate": round(parse_rate, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate floor pipeline outputs against golden expectations.")
    parser.add_argument("--pred-dir", required=True, help="Folder with *_data.json predictions")
    parser.add_argument("--expected-dir", required=True, help="Folder with expectation JSON files")
    parser.add_argument("--out-json", default="results/eval_report_v2.json", help="Output report path")
    parser.add_argument("--min-label-hit-rate", type=float, default=0.7)
    parser.add_argument("--min-dim-parse-rate", type=float, default=0.4)
    args = parser.parse_args()

    pred_dir = Path(args.pred_dir)
    exp_dir = Path(args.expected_dir)
    pred_files = sorted(pred_dir.glob("*_data.json"))
    rows: List[Dict] = []
    for pred_file in pred_files:
        expected_file = exp_dir / pred_file.name
        pred = _safe_load_json(pred_file)
        exp = _safe_load_json(expected_file) or {}
        if pred is None:
            continue
        metrics = evaluate_one(pred, exp)
        metrics["file"] = pred_file.name
        rows.append(metrics)

    total = len(rows)
    avg_label = sum(r["label_hit_rate"] for r in rows) / total if total else 0.0
    avg_parse = sum(r["dimension_parse_rate"] for r in rows) / total if total else 0.0
    avg_room_err = sum(r["room_count_error"] for r in rows) / total if total else 0.0
    summary = {
        "files": total,
        "avg_label_hit_rate": round(avg_label, 4),
        "avg_dimension_parse_rate": round(avg_parse, 4),
        "avg_room_count_error": round(avg_room_err, 4),
    }
    report = {"summary": summary, "files": rows}
    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[DONE] Evaluation report: {out_path}")

    failed = avg_label < args.min_label_hit_rate or avg_parse < args.min_dim_parse_rate
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
