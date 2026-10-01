from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "Ultralytics"))
os.environ.setdefault("ULTRALYTICS_CONFIG_DIR", str(ROOT / "Ultralytics"))

from pipeline import HybridFloorPlanPipeline, OCRConfig, ParseConfig, PipelineConfig
from pipeline.visualize import draw_final_overlay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hybrid AI Floor Plan Analysis Pipeline (v2)")
    parser.add_argument("--model", required=True, help="Path to YOLOv8 segmentation model (.pt)")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--image", help="Single floor plan image path")
    grp.add_argument("--dataset-dir", help="Directory of floor plan images")

    parser.add_argument("--output-dir", default="results/v2", help="Output folder for json/png outputs")
    parser.add_argument("--report-json", default="batch_verification_report_v4.json", help="Batch report file name")
    parser.add_argument("--use-gpu", action="store_true", help="Enable GPU for OCR")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"], help="Pipeline device mode")
    parser.add_argument("--gpu-profile", default="balanced", choices=["balanced", "max"], help="GPU load profile")
    parser.add_argument("--quiet-per-image", action="store_true", help="Disable per-image console logs")
    parser.add_argument("--no-visualize", action="store_true", help="Disable final overlay image export")
    parser.add_argument("--conf-yolo", type=float, default=0.35, help="YOLO confidence threshold")
    parser.add_argument("--conf-ocr", type=float, default=0.2, help="OCR min confidence threshold")
    parser.add_argument("--yolo-img-size", type=int, default=640, help="YOLO inference image size")
    parser.add_argument("--ocr-scale", type=int, default=3, help="OCR upscale factor")
    parser.add_argument("--ocr-alt-scale", type=float, default=0.0, help="Backward-compatible no-op in v2")
    parser.add_argument("--room-crop-pad", type=int, default=20, help="Padding around room crop before OCR")
    parser.add_argument("--ocr-mode", default="per_room", choices=["per_room", "full_image"], help="OCR mode")
    parser.add_argument("--ocr-two-pass-invert", action="store_true", help="Enable second OCR pass on inverted threshold")
    parser.add_argument("--ocr-no-threshold", action="store_true", help="Disable adaptive threshold preprocessing")
    parser.add_argument("--save-debug", action="store_true", help="Save per-room debug artifacts")
    parser.add_argument("--debug-dir", default="results/debug_v2", help="Debug output directory")
    parser.add_argument("--include-ocr-raw", action="store_true", help="Include raw OCR tokens in room JSON")
    parser.add_argument("--text-source", default="auto", choices=["auto", "pdf", "ocr"], help="Text source strategy")
    parser.add_argument("--ocr-engine", default="paddle", choices=["paddle", "easyocr"], help="Primary OCR engine")
    parser.add_argument("--ocr-dpi", type=int, default=600, help="OCR fallback rerender DPI for PDF crops")
    parser.add_argument("--min-pdf-words", type=int, default=8, help="Minimum PDF words to prefer pdf_text in auto mode")
    parser.add_argument("--save-text-debug", action="store_true", help="Save token overlays for chosen text source")
    parser.add_argument(
        "--disable-ocr-multi-scale",
        action="store_true",
        help="Kept for backward compatibility. v2 uses two-pass invert by default.",
    )
    parser.add_argument(
        "--frontend-format",
        action="store_true",
        help="Output frontend-ready JSON format (structured confidence, parsed dimensions)",
    )
    parser.add_argument(
        "--include-debug",
        action="store_true",
        help="Include debug payloads in frontend JSON output (OCR tokens, text blobs)",
    )
    return parser


def _iter_images(dataset_dir: str) -> List[Path]:
    root = Path(dataset_dir)
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts]
    return sorted(files)


def main() -> None:
    args = build_parser().parse_args()
    yolo_img_size = args.yolo_img_size
    if args.gpu_profile == "balanced":
        yolo_img_size = min(yolo_img_size, 768)

    cfg = PipelineConfig(
        model_path=args.model,
        yolo_img_size=yolo_img_size,
        yolo_conf=args.conf_yolo,
        room_crop_pad=args.room_crop_pad,
        ocr_mode=args.ocr_mode,
        include_ocr_raw=args.include_ocr_raw,
        save_debug=args.save_debug,
        debug_dir=args.debug_dir,
        device=args.device,
        text_source=args.text_source,
        min_pdf_words=args.min_pdf_words,
        save_text_debug=args.save_text_debug,
        text_debug_dir=str(Path(args.debug_dir) / "text_overlays"),
        ocr=OCRConfig(
            gpu=args.use_gpu,
            upscale=args.ocr_scale,
            min_conf_keep=args.conf_ocr,
            two_pass_invert=args.ocr_two_pass_invert,
            threshold=not args.ocr_no_threshold,
            engine=args.ocr_engine,
            ocr_dpi=args.ocr_dpi,
        ),
        parse=ParseConfig(),
    )
    pipe = HybridFloorPlanPipeline(cfg)
    if not args.quiet_per_image:
        print(f"[INFO] device={args.device} gpu_profile={args.gpu_profile} use_gpu_ocr={args.use_gpu}")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    images = [Path(args.image)] if args.image else _iter_images(args.dataset_dir)
    batch_items = []
    for idx, img_path in enumerate(images, start=1):
        if not args.quiet_per_image:
            print(f"[{idx}/{len(images)}] {img_path.name}")
        output = pipe.analyze_path(str(img_path))
        stem = img_path.stem
        json_path = out_dir / f"{stem}_data.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        # Generate frontend JSON if requested
        frontend_json_path = None
        if args.frontend_format:
            frontend_output = pipe.analyze_path_for_frontend(
                str(img_path),
                include_debug=args.include_debug,
            )
            frontend_json_path = out_dir / f"{stem}_frontend.json"
            with frontend_json_path.open("w", encoding="utf-8") as f:
                json.dump(frontend_output, f, indent=2, ensure_ascii=False)

        vis_path = None
        if not args.no_visualize:
            image = cv2.imread(str(img_path))
            overlay = draw_final_overlay(image, pipe.last_rooms)
            vis_path = out_dir / f"{stem}_result.png"
            cv2.imwrite(str(vis_path), overlay)
        batch_items.append({
            "image": str(img_path),
            "json": str(json_path),
            "frontend_json": str(frontend_json_path) if frontend_json_path else None,
            "viz": None if vis_path is None else str(vis_path),
        })

    report = {
        "pipeline_version": cfg.pipeline_version,
        "images_processed": len(images),
        "output_dir": str(out_dir),
        "items": batch_items,
    }
    report_path = out_dir / args.report_json
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[DONE] Report: {report_path}")


if __name__ == "__main__":
    main()
