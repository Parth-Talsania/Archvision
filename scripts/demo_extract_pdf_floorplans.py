from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from step1_pdf_extraction.brochure_pdf_extractor import BrochureFloorPlanExtractor


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo/verification for PDF floorplan extraction (Step-1 YOLO).")
    parser.add_argument("--model", required=True, help="Path to best.pt")
    parser.add_argument("--pdf", required=True, help="Path to brochure PDF")
    parser.add_argument("--output-dir", default="results/step1_demo", help="Output folder")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--min-area-ratio", type=float, default=0.03)
    parser.add_argument("--min-det-area-ratio", type=float, default=0.001)
    parser.add_argument("--min-component-detections", type=int, default=4)
    parser.add_argument("--component-close-kernel", type=int, default=31)
    parser.add_argument("--top-k-per-page", type=int, default=2)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    args = parser.parse_args()

    extractor = BrochureFloorPlanExtractor(
        yolo_model_path=args.model,
        dpi=args.dpi,
        yolo_conf=args.conf,
        yolo_iou=args.iou,
        yolo_imgsz=args.imgsz,
        min_area_ratio=args.min_area_ratio,
        min_det_area_ratio=args.min_det_area_ratio,
        min_component_detections=args.min_component_detections,
        component_close_kernel=args.component_close_kernel,
        top_k_per_page=args.top_k_per_page,
        save_debug=True,
        device=args.device,
    )
    manifest = extractor.extract_floorplan_pages(args.pdf, args.output_dir)
    selected = manifest.get("selected_images", [])
    kept = [d for d in manifest.get("decisions", []) if d.get("kept")]

    print(f"selected_images={len(selected)}")
    print(f"kept_detections={len(kept)}")
    for p in selected:
        print(p)

    assert len(selected) > 0, "No floorplan crops were produced."
    assert len(kept) >= len(selected), "Invalid state: outputs without kept detections."
    print("[OK] Verification checks passed.")


if __name__ == "__main__":
    main()
