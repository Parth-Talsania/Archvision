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

from pdf_extract import ExtractConfig

from .orchestrator import run_full_pipeline
from .schemas import AnalyzerConfig, FullPipelineOptions


def _str2bool(v: str) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Merged full pipeline: PDF -> extracted plans -> room analysis")
    p.add_argument("--pdf", required=True, help="Input PDF path")
    p.add_argument("--out_dir", required=True, help="Output root directory")

    # Extractor pass-through
    p.add_argument("--dpi", type=int, default=450)
    p.add_argument("--thumb_dpi", type=int, default=120)
    p.add_argument("--max_pages", type=int, default=None)
    p.add_argument("--min_page_score", type=float, default=0.55)
    p.add_argument("--min_crop_score", type=float, default=0.60)
    p.add_argument("--max_regions_per_page", type=int, default=4)
    p.add_argument("--min_region_area_ratio", type=float, default=0.05)
    p.add_argument("--pad_px", type=int, default=20)
    p.add_argument("--validator", choices=["none", "yolo"], default="yolo")
    p.add_argument("--min_rooms", type=int, default=3)
    p.add_argument("--scan_all_pages", action="store_true", default=True)
    p.add_argument("--no-scan_all_pages", dest="scan_all_pages", action="store_false")
    p.add_argument("--rescue_top_pages", type=int, default=8)
    p.add_argument("--target_long_side", type=int, default=4096)
    p.add_argument("--save_debug_extractor", action="store_true")

    # Analyzer pass-through
    p.add_argument("--yolo_model", required=True, help="YOLO model path used for analyzer and extractor validator")
    p.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    p.add_argument("--use_gpu_ocr", action="store_true")
    p.add_argument("--ocr_mode", choices=["per_room", "full_image"], default="per_room")
    p.add_argument("--include_ocr_raw", action="store_true")
    p.add_argument("--save_debug_analyzer", action="store_true")
    p.add_argument("--yolo_img_size", type=int, default=640)
    p.add_argument("--conf_yolo", type=float, default=0.35)
    p.add_argument("--conf_ocr", type=float, default=0.2)
    p.add_argument("--room_crop_pad", type=int, default=20)
    p.add_argument("--ocr_scale", type=int, default=3)
    p.add_argument("--ocr_two_pass_invert", action="store_true")
    p.add_argument("--ocr_no_threshold", action="store_true")
    p.add_argument("--text-source", choices=["auto", "pdf", "ocr"], default="auto")
    p.add_argument("--ocr-engine", choices=["paddle", "easyocr"], default="paddle")
    p.add_argument("--ocr-dpi", type=int, default=600)
    p.add_argument("--min-pdf-words", type=int, default=8)
    p.add_argument("--save-text-debug", action="store_true")
    p.add_argument("--debug-dir", default=None, help="Base debug directory (default: <out_dir>/debug)")

    # Orchestration
    p.add_argument("--resume", action="store_true")
    p.add_argument("--embed-analysis-json", nargs="?", const="true", default="false")
    p.add_argument("--stop-on-first-failure", action="store_true")
    p.add_argument("--max_plans", type=int, default=None)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--export-polygons-page-coords", action="store_true")
    return p


def main() -> None:
    args = build_parser().parse_args()

    extractor_cfg = ExtractConfig(
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
        save_debug=args.save_debug_extractor,
        debug_dir=None,
        validator=args.validator,
        yolo_model=args.yolo_model,
        min_rooms=args.min_rooms,
        device=args.device,
        scan_all_pages=args.scan_all_pages,
        rescue_top_pages=args.rescue_top_pages,
        target_long_side=args.target_long_side,
    )
    analyzer_cfg = AnalyzerConfig(
        model_path=args.yolo_model,
        device=args.device,
        use_gpu_ocr=args.use_gpu_ocr,
        yolo_img_size=args.yolo_img_size,
        conf_yolo=args.conf_yolo,
        conf_ocr=args.conf_ocr,
        room_crop_pad=args.room_crop_pad,
        ocr_mode=args.ocr_mode,
        ocr_scale=args.ocr_scale,
        ocr_two_pass_invert=args.ocr_two_pass_invert,
        ocr_no_threshold=args.ocr_no_threshold,
        include_ocr_raw=args.include_ocr_raw,
        save_debug_analyzer=args.save_debug_analyzer,
        debug_dir=str((Path(args.debug_dir) if args.debug_dir else Path(args.out_dir) / "debug") / "analyzer"),
        text_source=args.text_source,
        ocr_engine=args.ocr_engine,
        ocr_dpi=args.ocr_dpi,
        min_pdf_words=args.min_pdf_words,
        save_text_debug=args.save_text_debug,
    )
    opts = FullPipelineOptions(
        resume=args.resume,
        embed_analysis_json=_str2bool(args.embed_analysis_json),
        stop_on_first_failure=args.stop_on_first_failure,
        max_plans=args.max_plans,
        workers=args.workers,
        log_level=args.log_level,
        export_polygons_page_coords=args.export_polygons_page_coords,
        save_debug_extractor=args.save_debug_extractor,
    )

    exit_code = 0
    try:
        final_json = run_full_pipeline(
            pdf_path=args.pdf,
            out_dir=args.out_dir,
            extractor_config=extractor_cfg,
            analyzer_config=analyzer_cfg,
            options=opts,
        )
        print(f"[DONE] final_output.json: {final_json}")
    except Exception as e:
        print(f"[ERROR] {e}")
        exit_code = 2
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
