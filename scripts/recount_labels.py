"""Recompute the labelled-room counts of stored analyses.

Older versions only counted a room as labelled when its label differed from
the YOLO class name, so rooms such as "Hall" (OCR and YOLO agree) were left
out. This updates the ``rooms_with_labels`` column and the per-page summaries
inside ``result_json`` using pipeline.frontend_schema.has_room_label.

Usage:
    python scripts/recount_labels.py           # show what would change
    python scripts/recount_labels.py --apply   # write the changes
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal  # noqa: E402
from backend.models import AnalysisJob  # noqa: E402
from pipeline.frontend_schema import has_room_label  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="Write the changes to the database")
    args = parser.parse_args()

    db = SessionLocal()
    changed = 0
    try:
        jobs = db.query(AnalysisJob).filter(AnalysisJob.result_json.isnot(None)).all()
        for job in jobs:
            try:
                result = json.loads(job.result_json)
            except json.JSONDecodeError:
                continue
            pages = result.get("pages") or []
            total = 0
            for page in pages:
                count = sum(1 for r in page.get("rooms", []) if has_room_label(r.get("label")))
                if isinstance(page.get("summary"), dict):
                    page["summary"]["rooms_with_labels"] = count
                total += count
            if not pages or total == job.rooms_with_labels:
                continue
            print(f"job {job.id:>5}  {job.filename[:40]:40}  labels {job.rooms_with_labels} -> {total}")
            changed += 1
            if args.apply:
                job.rooms_with_labels = total
                job.result_json = json.dumps(result, ensure_ascii=False)
        if args.apply:
            db.commit()
    finally:
        db.close()

    action = "Updated" if args.apply else "Would update"
    print(f"{action} {changed} of {len(jobs)} analyses.")


if __name__ == "__main__":
    main()
