from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "Ultralytics"))
os.environ.setdefault("ULTRALYTICS_CONFIG_DIR", str(ROOT / "Ultralytics"))

from .pdf_to_floorplans import ExtractConfig, PDFFloorPlanExtractor


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Extract 2D floor plan image regions from brochure PDFs.")
    p.add_argument("--pdf", required=True, help="Input PDF path")
    p.add_argument("--out_dir", required=True, help="Output directory")
    p.add_argument("--dpi", type=int, default=450)
    p.add_argument("--thumb_dpi", type=int, default=120)
    p.add_argument("--max_pages", type=int, default=None)
    p.add_argument("--min_page_score", type=float, default=0.55)
    p.add_argument("--min_crop_score", type=float, default=0.60)
    p.add_argument("--max_regions_per_page", type=int, default=4)
    p.add_argument("--min_region_area_ratio", type=float, default=0.05)
    p.add_argument("--pad_px", type=int, default=20)
    p.add_argument("--save_debug", action="store_true")
    p.add_argument("--debug_dir", default=None)
    p.add_argument("--validator", choices=["none", "yolo"], default="yolo")
    p.add_argument("--yolo_model", default=None)
    p.add_argument("--min_rooms", type=int, default=3)
    p.add_argument("--device", choices=["cpu", "cuda", "auto"], default="auto")
    p.add_argument("--scan_all_pages", action="store_true", default=True, help="Process all pages (recommended).")
    p.add_argument("--no-scan_all_pages", dest="scan_all_pages", action="store_false", help="Enable page pre-filtering before heavy pass.")
    p.add_argument("--rescue_top_pages", type=int, default=8, help="If pre-filtering is enabled, also inspect top-N pages by image score.")
    p.add_argument("--target-long-side", type=int, default=4096, help="Upscale page render so long side reaches this size (0 to disable).")
    return p


def main() -> None:
    args = build_parser().parse_args()
    cfg = ExtractConfig(
        pdf=args.pdf,
        out_dir=args.out_dir,
        dpi=args.dpi,
        thumb_dpi=args.thumb_dpi,
        max_pages=args.max_pages,
        min_page_score=args.min_page_score,
        min_crop_score=args.min_crop_score,
        max_regions_per_page=args.max_regions_per_page,
        min_region_area_ratio=args.min_region_area_ratio,
        pad_px=args.pad_px,
        save_debug=args.save_debug,
        debug_dir=args.debug_dir,
        validator=args.validator,
        yolo_model=args.yolo_model,
        min_rooms=args.min_rooms,
        device=args.device,
        scan_all_pages=args.scan_all_pages,
        rescue_top_pages=args.rescue_top_pages,
        target_long_side=args.target_long_side,
    )
    extractor = PDFFloorPlanExtractor(cfg)
    summary = extractor.run()
    print(f"PDF: {summary['pdf']}")
    print(f"Extracted crops: {summary['extracted_count']}")
    print(f"Pages with floorplans: {summary['pages_with_floorplans']}")
    print(f"Manifest: {Path(args.out_dir) / 'manifest.json'}")


if __name__ == "__main__":
    main()
