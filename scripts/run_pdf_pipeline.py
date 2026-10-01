from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "Ultralytics"))
os.environ.setdefault("ULTRALYTICS_CONFIG_DIR", str(ROOT / "Ultralytics"))

from pdf_extract import ExtractConfig, PDFFloorPlanExtractor
from pdf_extract.image_extractor import PDFImageExtractor, ExtractionConfig
from pipeline import HybridFloorPlanPipeline, OCRConfig, ParseConfig, PipelineConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Full pipeline: PDF -> floorplan crops -> v2 segmentation+OCR")
    parser.add_argument("--model", required=True, help="Path to YOLOv8 segmentation model (.pt)")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--pdf", help="Single brochure PDF file")
    grp.add_argument("--pdf-dir", help="Folder with brochure PDFs")

    parser.add_argument("--output-dir", default="results/full_pipeline", help="Output root")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"], help="Device mode")
    parser.add_argument("--use-gpu", action="store_true", help="Enable GPU for OCR")
    parser.add_argument("--quiet", action="store_true", help="Reduce logging")

    # Step 1: PDF -> floorplan crops
    parser.add_argument("--step1-dpi", type=int, default=450)
    parser.add_argument("--step1-thumb-dpi", type=int, default=120)
    parser.add_argument("--step1-max-pages", type=int, default=None)
    parser.add_argument("--step1-min-page-score", type=float, default=0.55)
    parser.add_argument("--step1-min-crop-score", type=float, default=0.60)
    parser.add_argument("--step1-max-regions-per-page", type=int, default=4)
    parser.add_argument("--step1-min-region-area-ratio", type=float, default=0.05)
    parser.add_argument("--step1-pad-px", type=int, default=20)
    parser.add_argument("--step1-validator", choices=["none", "yolo"], default="yolo")
    parser.add_argument("--step1-min-rooms", type=int, default=3)
    parser.add_argument("--step1-scan-all-pages", action="store_true", default=True)
    parser.add_argument("--step1-no-scan-all-pages", dest="step1_scan_all_pages", action="store_false")
    parser.add_argument("--step1-rescue-top-pages", type=int, default=8)
    parser.add_argument("--step1-target-long-side", type=int, default=4096)
    parser.add_argument("--step1-save-debug", action="store_true")
    
    # NEW: Use direct embedded image extraction (recommended)
    parser.add_argument("--step1-use-embedded", action="store_true", default=True,
                        help="Use direct embedded image extraction (preserves quality)")
    parser.add_argument("--step1-no-embedded", dest="step1_use_embedded", action="store_false",
                        help="Use old page-render extraction method")
    parser.add_argument("--step1-min-embedded-size", type=int, default=400,
                        help="Minimum dimension for embedded images")

    # Step 2: v2 segmentation + OCR
    parser.add_argument("--conf-yolo", type=float, default=0.35)
    parser.add_argument("--conf-ocr", type=float, default=0.2)
    parser.add_argument("--yolo-img-size", type=int, default=640)
    parser.add_argument("--room-crop-pad", type=int, default=20)
    parser.add_argument("--ocr-mode", default="per_room", choices=["per_room", "full_image"])
    parser.add_argument("--ocr-scale", type=int, default=3)
    parser.add_argument("--ocr-two-pass-invert", action="store_true")
    parser.add_argument("--ocr-no-threshold", action="store_true")
    parser.add_argument("--include-ocr-raw", action="store_true")
    parser.add_argument("--step2-save-debug", action="store_true")
    parser.add_argument("--step2-debug-dir", default="results/debug_full_pipeline")
    return parser


def _iter_pdfs(pdf_dir: str) -> List[Path]:
    root = Path(pdf_dir)
    return sorted([p for p in root.rglob("*.pdf") if p.is_file()])


def _build_v2_pipeline(args: argparse.Namespace) -> HybridFloorPlanPipeline:
    cfg = PipelineConfig(
        model_path=args.model,
        yolo_img_size=args.yolo_img_size,
        yolo_conf=args.conf_yolo,
        room_crop_pad=args.room_crop_pad,
        ocr_mode=args.ocr_mode,
        include_ocr_raw=args.include_ocr_raw,
        save_debug=args.step2_save_debug,
        debug_dir=args.step2_debug_dir,
        device=args.device,
        ocr=OCRConfig(
            gpu=args.use_gpu,
            upscale=args.ocr_scale,
            min_conf_keep=args.conf_ocr,
            two_pass_invert=args.ocr_two_pass_invert,
            threshold=not args.ocr_no_threshold,
        ),
        parse=ParseConfig(),
    )
    return HybridFloorPlanPipeline(cfg)


def _draw_overlay_clean(image, rooms):
    vis = image.copy()
    for room in rooms:
        pts = room.polygon_simplified.exterior.coords
        poly = []
        for x, y in pts:
            poly.append([int(round(x)), int(round(y))])
        if len(poly) < 3:
            continue
        p = np.asarray(poly, dtype=np.int32)
        cv2.polylines(vis, [p], isClosed=True, color=(255, 255, 0), thickness=2)
        cx, cy = int(room.centroid[0]), int(room.centroid[1])
        # Keep segmentation label, and include OCR text only when dimensions are present.
        label = room.class_name
        if room.dimensions_text:
            label = f"{label} | {room.dimensions_text}"
        cv2.putText(vis, label[:72], (cx - 90, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
    return vis


def _run_step1_embedded(pdf_path: Path, step1_dir: Path, args: argparse.Namespace) -> Dict:
    """NEW: Extract embedded images directly (preserves original quality)."""
    floorplans_dir = step1_dir / "floorplans"
    floorplans_dir.mkdir(parents=True, exist_ok=True)
    
    config = ExtractionConfig(
        min_embedded_size=args.step1_min_embedded_size,
        min_embedded_area_ratio=0.1,
        render_dpi=args.step1_dpi,  # Fallback DPI
        target_long_side=0,  # Don't resize extracted images
        min_quality_score=0.3,
        save_debug=args.step1_save_debug,
    )
    
    extractor = PDFImageExtractor(config)
    results = extractor.extract_from_pdf(pdf_path, output_dir=step1_dir)
    
    # Convert to manifest format expected by Step 2
    # NOTE: filenames must match _save_results() in image_extractor.py
    # which uses _e{idx+1} as suffix for embedded images (global index)
    items = []
    for idx, r in enumerate(results):
        filename = f"{pdf_path.stem}_p{r.page_index+1:02d}"
        if r.extraction_method == "embedded":
            filename += f"_e{idx+1}"
        filename += ".png"
        
        items.append({
            "page_number": r.page_index + 1,
            "output_image": f"floorplans/{filename}",
            "extraction_method": r.extraction_method,
            "quality_score": r.quality_score,
            "width": r.final_size[0],
            "height": r.final_size[1],
        })
    
    manifest = {
        "pdf": str(pdf_path),
        "extraction_method": "embedded_priority",
        "extracted_count": len(items),
        "embedded_count": sum(1 for r in results if r.extraction_method == "embedded"),
        "rendered_count": sum(1 for r in results if r.extraction_method == "rendered"),
        "items": items,
    }
    
    # Save manifest
    manifest_path = step1_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        import json
        json.dump(manifest, f, indent=2)
    
    return manifest


def _run_step1_extract(pdf_path: Path, step1_dir: Path, args: argparse.Namespace) -> Dict:
    """OLD: Page-render extraction method."""
    cfg = ExtractConfig(
        pdf=str(pdf_path),
        out_dir=str(step1_dir),
        dpi=args.step1_dpi,
        thumb_dpi=args.step1_thumb_dpi,
        max_pages=args.step1_max_pages,
        min_page_score=args.step1_min_page_score,
        min_crop_score=args.step1_min_crop_score,
        max_regions_per_page=args.step1_max_regions_per_page,
        min_region_area_ratio=args.step1_min_region_area_ratio,
        pad_px=args.step1_pad_px,
        save_debug=args.step1_save_debug,
        debug_dir=None,
        validator=args.step1_validator,
        yolo_model=args.model,
        min_rooms=args.step1_min_rooms,
        device=args.device,
        scan_all_pages=args.step1_scan_all_pages,
        rescue_top_pages=args.step1_rescue_top_pages,
        target_long_side=args.step1_target_long_side,
    )
    extractor = PDFFloorPlanExtractor(cfg)
    return extractor.run()


def run_for_pdf(pdf_path: Path, args: argparse.Namespace, pipe: HybridFloorPlanPipeline) -> Dict:
    pdf_out = Path(args.output_dir) / pdf_path.stem
    step1_dir = pdf_out / "step1"
    step2_dir = pdf_out / "step2"
    step1_dir.mkdir(parents=True, exist_ok=True)
    step2_dir.mkdir(parents=True, exist_ok=True)

    # Choose extraction method
    if args.step1_use_embedded:
        if not args.quiet:
            print("  [STEP1] Using direct embedded extraction (NEW method)")
        step1_manifest = _run_step1_embedded(pdf_path, step1_dir, args)
    else:
        if not args.quiet:
            print("  [STEP1] Using page-render extraction (OLD method)")
        step1_manifest = _run_step1_extract(pdf_path, step1_dir, args)
    items = []
    floorplan_items = step1_manifest.get("items", [])
    for idx, extracted in enumerate(floorplan_items, start=1):
        rel_img = extracted.get("output_image")
        if not rel_img:
            continue
        img_path = step1_dir / rel_img
        if not img_path.exists():
            continue
        if not args.quiet:
            print(f"  [STEP2 {idx}/{len(floorplan_items)}] {img_path.name}")
        out = pipe.analyze_path(str(img_path))

        stem = img_path.stem
        json_path = step2_dir / f"{stem}_data.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

        src = cv2.imread(str(img_path))
        overlay = _draw_overlay_clean(src, pipe.last_rooms)
        png_path = step2_dir / f"{stem}_result.png"
        cv2.imwrite(str(png_path), overlay)

        items.append(
            {
                "input_image": str(img_path),
                "source_page_number": extracted.get("page_number"),
                "source_bbox_px": extracted.get("bbox_px"),
                "json": str(json_path),
                "viz": str(png_path),
                "total_rooms": out.get("total_rooms", 0),
            }
        )

    report = {
        "pdf": str(pdf_path),
        "step1_manifest": str(step1_dir / "manifest.json"),
        "step1_extracted_count": len(floorplan_items),
        "step2_processed_images": len(items),
        "items": items,
    }
    with (pdf_out / "full_pipeline_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report


def main() -> None:
    args = build_parser().parse_args()
    out_root = Path(args.output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    pdfs = [Path(args.pdf)] if args.pdf else _iter_pdfs(args.pdf_dir)
    pipe = _build_v2_pipeline(args)
    if not args.quiet:
        print(f"[INFO] device={args.device} use_gpu_ocr={args.use_gpu}")

    all_reports = []
    for i, pdf in enumerate(pdfs, start=1):
        if not args.quiet:
            print(f"[{i}/{len(pdfs)}] Processing {pdf}")
        all_reports.append(run_for_pdf(pdf, args, pipe))

    batch = {"total_pdfs": len(pdfs), "reports": all_reports}
    batch_path = out_root / "full_pipeline_batch_report.json"
    with batch_path.open("w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)
    print(f"[DONE] Batch report: {batch_path}")


if __name__ == "__main__":
    main()
