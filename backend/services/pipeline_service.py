"""
Pipeline service: wraps the existing floor plan analysis pipeline
for use by the FastAPI backend.

Follows the same flow as the Kaggle Output kaggle_notebook.ipynb:
  - Cell 4 (single image): scripts/run_pipeline.py flow
  - Cell 8 (PDF):          scripts/run_pdf_pipeline.py flow
                            using PDFFloorPlanExtractor (Step 1)
                            which scores pages + validates with YOLO
                            so only real 2D floor plans are extracted.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np

# Ensure project root is on sys.path so we can import pipeline/ and pdf_extract/
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

os.environ.setdefault("YOLO_CONFIG_DIR", str(_PROJECT_ROOT / "Ultralytics"))
os.environ.setdefault("ULTRALYTICS_CONFIG_DIR", str(_PROJECT_ROOT / "Ultralytics"))

from pipeline import HybridFloorPlanPipeline, OCRConfig, ParseConfig, PipelineConfig
from pipeline.frontend_schema import (
    has_room_label,
    SCHEMA_VERSION,
    build_frontend_output,
    convert_legacy_output_to_frontend,
)
from pipeline.visualize import draw_final_overlay, build_color_legend, get_room_color_hex

# PDFFloorPlanExtractor — the smart extractor used by Kaggle Cell 8.
# It renders pages, scores them by text keywords + image features,
# detects candidate regions via edge/morphology analysis,
# then validates each crop with YOLO (only keeps crops with >= min_rooms).
from pdf_extract import ExtractConfig, PDFFloorPlanExtractor

from backend.config import MODEL_PATH, RESULTS_DIR


# ---------------------------------------------------------------------------
# Progress queues for SSE streaming (keyed by job_id)
# ---------------------------------------------------------------------------

_progress_queues: Dict[int, queue.Queue] = {}


def get_progress_queue(job_id: int) -> queue.Queue:
    if job_id not in _progress_queues:
        _progress_queues[job_id] = queue.Queue(maxsize=200)
    return _progress_queues[job_id]


def remove_progress_queue(job_id: int):
    _progress_queues.pop(job_id, None)


# ---------------------------------------------------------------------------
# Singleton pipeline instance (loaded once, reused)
# ---------------------------------------------------------------------------

_pipeline_instance: Optional[HybridFloorPlanPipeline] = None


def _get_pipeline() -> HybridFloorPlanPipeline:
    """
    Return (and lazily create) the singleton pipeline.

    Config matches scripts/run_pipeline.py defaults used by Kaggle Cell 4:
      --ocr-engine paddle  --ocr-scale 3  --conf-yolo 0.35
      --yolo-img-size 640  --room-crop-pad 20  --ocr-mode per_room
    """
    global _pipeline_instance
    if _pipeline_instance is None:
        cfg = PipelineConfig(
            model_path=MODEL_PATH,
            yolo_img_size=640,
            yolo_conf=0.35,
            room_crop_pad=20,
            ocr_mode="hybrid",
            device="auto",
            ocr=OCRConfig(
                gpu=False,
                upscale=3,
                two_pass_invert=False,
                adaptive_scale=True,
                engine="easyocr",
                watermark_filter=True,
            ),
            parse=ParseConfig(),
        )
        _pipeline_instance = HybridFloorPlanPipeline(cfg)
    return _pipeline_instance


# ---------------------------------------------------------------------------
# Single image analysis  (mirrors Kaggle Cell 4 / scripts/run_pipeline.py)
# ---------------------------------------------------------------------------


def analyze_image(
    image_path: str,
    job_id: int,
) -> Dict[str, Any]:
    """
    Run the full analysis pipeline on a single image.

    Flow (same as scripts/run_pipeline.py with --frontend-format --include-debug):
      1. pipe.analyze_path(image_path) -> legacy output
      2. Save legacy JSON
      3. Build frontend JSON via build_frontend_output(pipe.last_rooms)
      4. draw_final_overlay -> save overlay PNG
    """
    pipe = _get_pipeline()

    # 1. Run pipeline  (same as Cell 4 line: output = pipe.analyze_path(str(img_path)))
    legacy_output = pipe.analyze_path(image_path)

    # 2. Save raw legacy JSON  (same as Cell 4: json.dump(output, f))
    job_dir = RESULTS_DIR / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    json_path = job_dir / "result.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(legacy_output, f, indent=2, ensure_ascii=False)

    # 3. Build frontend JSON using pipe.last_rooms
    #    (same as Cell 4: pipe.analyze_path_for_frontend -> build_frontend_output)
    src_img = cv2.imread(image_path)
    h, w = (src_img.shape[:2]) if src_img is not None else (0, 0)
    text_meta = legacy_output.get("text_metadata", {})
    text_strategy = text_meta.get("text_source_used", "unknown")

    frontend_json = build_frontend_output(
        image_path=image_path,
        image_width=w,
        image_height=h,
        rooms=pipe.last_rooms,
        text_strategy=text_strategy,
        include_debug=True,
        source_type="image",
    )

    # Patch image_path to an API-accessible URL
    upload_filename = Path(image_path).name
    if frontend_json.get("pages"):
        frontend_json["pages"][0]["image_path"] = f"/api/files/uploads/{upload_filename}"

    # Add colour legend + per-room colour
    if pipe.last_rooms:
        legend = build_color_legend(pipe.last_rooms)
        frontend_json["color_legend"] = legend
        if frontend_json.get("pages"):
            for room_data in frontend_json["pages"][0].get("rooms", []):
                lbl = room_data.get("label") or "room"
                room_data["color"] = get_room_color_hex(lbl)

    # 4. Overlay visualization  (same as Cell 4: draw_final_overlay)
    result_image_path: Optional[str] = None
    if src_img is not None and pipe.last_rooms:
        overlay = draw_final_overlay(src_img, pipe.last_rooms)
        viz_path = job_dir / "result_overlay.png"
        cv2.imwrite(str(viz_path), overlay)
        result_image_path = str(viz_path)

    # Summary stats from rooms
    total_rooms = len(pipe.last_rooms)
    rooms_with_labels = sum(1 for r in pipe.last_rooms if has_room_label(r.label))
    rooms_with_dimensions = sum(1 for r in pipe.last_rooms if r.dimensions_text)

    return {
        "result_json": frontend_json,
        "result_image_path": result_image_path,
        "total_rooms": total_rooms,
        "rooms_with_labels": rooms_with_labels,
        "rooms_with_dimensions": rooms_with_dimensions,
    }


# ---------------------------------------------------------------------------
# PDF analysis  (mirrors Kaggle Cell 8 / scripts/run_pdf_pipeline.py)
#
# Step 1 — PDFFloorPlanExtractor (_run_step1_extract):
#   Renders thumbnail (120 DPI) -> text + image scoring per page
#   Renders full-res (450 DPI) -> YOLO validation on full page
#   Edge/morphology region detection -> candidate crops
#   YOLO validation per crop -> only accepts crops with >= min_rooms
#   Result: ONLY actual 2D floor plan crops are extracted.
#
# Step 2 — for each validated floor plan crop:
#   pipe.analyze_path(img_path)  (segmentation + OCR)
# ---------------------------------------------------------------------------


def analyze_pdf(
    pdf_path: str,
    job_id: int,
) -> Dict[str, Any]:
    """
    Run full pipeline on a PDF, matching scripts/run_pdf_pipeline.py:

      Step 1  PDFFloorPlanExtractor (same as _run_step1_extract):
              Scores pages by text keywords + image features,
              detects candidate regions via edge detection,
              validates each crop with YOLO (min 3 rooms).
              Only real 2D floor plans pass through.

      Step 2  pipe.analyze_path() on each extracted floor plan crop
              (same as run_for_pdf's step-2 loop).
    """
    pipe = _get_pipeline()
    job_dir = RESULTS_DIR / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    step1_dir = job_dir / "step1"
    step1_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: PDFFloorPlanExtractor — same config as Kaggle Cell 8
    # (defaults from scripts/run_pdf_pipeline.py build_parser())
    # ------------------------------------------------------------------
    extract_cfg = ExtractConfig(
        pdf=pdf_path,
        out_dir=str(step1_dir),
        dpi=450,                     # --step1-dpi 450
        thumb_dpi=120,               # --step1-thumb-dpi 120
        max_pages=None,              # process all pages
        min_page_score=0.55,         # --step1-min-page-score 0.55
        min_crop_score=0.60,         # --step1-min-crop-score 0.60
        max_regions_per_page=4,      # --step1-max-regions-per-page 4
        min_region_area_ratio=0.05,  # --step1-min-region-area-ratio 0.05
        pad_px=20,                   # --step1-pad-px 20
        save_debug=False,
        debug_dir=None,
        validator="yolo",            # --step1-validator yolo
        yolo_model=MODEL_PATH,       # same YOLO model used by pipeline
        min_rooms=3,                 # --step1-min-rooms 3
        device="auto",
        scan_all_pages=True,         # --step1-scan-all-pages (default True)
        rescue_top_pages=8,          # --step1-rescue-top-pages 8
        target_long_side=4096,       # --step1-target-long-side 4096
    )

    try:
        extractor = PDFFloorPlanExtractor(extract_cfg)
        step1_manifest = extractor.run()
    except RuntimeError as e:
        # PDFFloorPlanExtractor raises RuntimeError when no floor plans found
        print(f"[PDF] No floor plans extracted: {e}")
        return {
            "result_json": {"error": f"No floor plan images detected in PDF: {e}"},
            "result_image_path": None,
            "total_rooms": 0,
            "rooms_with_labels": 0,
            "rooms_with_dimensions": 0,
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "result_json": {"error": f"PDF extraction failed: {e}"},
            "result_image_path": None,
            "total_rooms": 0,
            "rooms_with_labels": 0,
            "rooms_with_dimensions": 0,
        }

    floorplan_items = step1_manifest.get("items", [])
    if not floorplan_items:
        return {
            "result_json": {"error": "No floor plan images detected in PDF"},
            "result_image_path": None,
            "total_rooms": 0,
            "rooms_with_labels": 0,
            "rooms_with_dimensions": 0,
        }

    # ------------------------------------------------------------------
    # Step 2: Analyse each extracted floor plan crop
    # (same as Kaggle run_for_pdf step-2 loop)
    # ------------------------------------------------------------------
    all_pages: List[Dict] = []
    extracted_images: List[Dict] = []
    overlay_images: List[Dict] = []
    all_legend_items: Dict[str, str] = {}
    total_rooms = 0
    total_labels = 0
    total_dims = 0
    result_idx = 0

    for idx, extracted in enumerate(floorplan_items, start=1):
        rel_img = extracted.get("output_image")
        if not rel_img:
            continue
        img_path = step1_dir / rel_img
        if not img_path.exists():
            continue

        try:
            print(f"  [STEP2 {idx}/{len(floorplan_items)}] {img_path.name}")

            # Run pipeline — same as Cell 8: out = pipe.analyze_path(str(img_path))
            legacy_output = pipe.analyze_path(str(img_path))
            rooms = legacy_output.get("rooms", [])

            # Skip images where no rooms detected
            if not rooms:
                continue

            result_idx += 1
            floor_plan_img = cv2.imread(str(img_path))
            if floor_plan_img is None:
                continue

            # Copy extracted image into job dir for API serving
            extracted_filename = f"extracted_page_{result_idx}.png"
            cv2.imwrite(str(job_dir / extracted_filename), floor_plan_img)

            extracted_images.append({
                "page": result_idx,
                "source_page_number": extracted.get("page_number"),
                "url": f"/api/files/results/{job_id}/{extracted_filename}",
            })

            # Save per-image raw result JSON
            per_img_json = job_dir / f"result_page_{result_idx}.json"
            with per_img_json.open("w", encoding="utf-8") as f:
                json.dump(legacy_output, f, indent=2, ensure_ascii=False)

            total_rooms += len(rooms)
            total_labels += sum(1 for r in rooms if has_room_label(r.get("label")))
            total_dims += sum(1 for r in rooms if r.get("dimensions_text"))

            # Generate overlay  (same as Cell 8: overlay = _draw_overlay_clean / draw_final_overlay)
            overlay_filename = f"result_page_{result_idx}_overlay.png"
            if pipe.last_rooms:
                overlay = draw_final_overlay(floor_plan_img, pipe.last_rooms)
                cv2.imwrite(str(job_dir / overlay_filename), overlay)
                overlay_images.append({
                    "page": result_idx,
                    "url": f"/api/files/results/{job_id}/{overlay_filename}",
                })
                for legend_item in build_color_legend(pipe.last_rooms):
                    all_legend_items[legend_item["label"]] = legend_item["color"]

            # Build frontend-schema page from pipe.last_rooms
            img_h, img_w = floor_plan_img.shape[:2]
            text_meta = legacy_output.get("text_metadata", {})
            text_strategy = text_meta.get("text_source_used", "unknown")

            page_frontend = build_frontend_output(
                image_path=str(img_path),
                image_width=img_w,
                image_height=img_h,
                rooms=pipe.last_rooms,
                text_strategy=text_strategy,
                include_debug=True,
                source_type="pdf",
                page_index=result_idx - 1,
            )
            if page_frontend.get("pages"):
                page_data = page_frontend["pages"][0]
                page_data["image_path"] = f"/api/files/results/{job_id}/{extracted_filename}"
                page_data["overlay_path"] = f"/api/files/results/{job_id}/{overlay_filename}"
                page_data["source_page_number"] = extracted.get("page_number")
                page_data["page_score"] = extracted.get("page_score")
                page_data["crop_score"] = extracted.get("crop_score")
                page_data["yolo_room_count"] = extracted.get("yolo_room_count")
                for room_data in page_data.get("rooms", []):
                    lbl = room_data.get("label") or "room"
                    room_data["color"] = get_room_color_hex(lbl)
                all_pages.append(page_data)

        except Exception:
            traceback.print_exc()
            continue

    # ------------------------------------------------------------------
    # Step 3: Build combined frontend-schema output
    # ------------------------------------------------------------------
    if not all_pages:
        return {
            "result_json": {"error": "No floor plan images detected in PDF"},
            "result_image_path": None,
            "total_rooms": 0,
            "rooms_with_labels": 0,
            "rooms_with_dimensions": 0,
        }

    color_legend = [
        {"label": lbl, "color": clr} for lbl, clr in all_legend_items.items()
    ]
    combined: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "type": "pdf",
            "file": Path(pdf_path).name,
            "dpi": 450,
            "total_pages": len(all_pages),
            "step1_extracted_count": len(floorplan_items),
            "step1_pages_with_floorplans": step1_manifest.get("pages_with_floorplans", []),
        },
        "pages": all_pages,
        "extracted_images": extracted_images,
        "overlay_images": overlay_images,
        "color_legend": color_legend,
    }

    combined_path = job_dir / "result.json"
    with combined_path.open("w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    first_overlay = job_dir / "result_page_1_overlay.png"
    result_image = str(first_overlay) if first_overlay.exists() else None

    return {
        "result_json": combined,
        "result_image_path": result_image,
        "total_rooms": total_rooms,
        "rooms_with_labels": total_labels,
        "rooms_with_dimensions": total_dims,
    }


# ---------------------------------------------------------------------------
# Background PDF processing (runs in a thread, updates DB when done)
# ---------------------------------------------------------------------------


def run_pdf_background(pdf_path: str, job_id: int):
    """
    Entry point for background thread. Runs analyze_pdf, pushes progress
    events to the shared queue, and updates the DB on completion/failure.
    """
    from backend.database import SessionLocal
    from backend.models import AnalysisJob

    q = get_progress_queue(job_id)

    def _push(step: str, page: int, total: int, msg: str):
        try:
            q.put_nowait({"step": step, "page": page, "total": total, "message": msg})
        except queue.Full:
            pass

    try:
        _push("processing", 0, 0, "Starting PDF analysis...")
        result = analyze_pdf(pdf_path, job_id)
        _push("completed", 0, 0, "Analysis complete")

        db = SessionLocal()
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job:
                if "error" in (result.get("result_json") or {}):
                    job.status = "failed"
                    job.error_message = result["result_json"].get("error", "Unknown error")[:2000]
                else:
                    job.status = "completed"
                job.result_json = json.dumps(result["result_json"], ensure_ascii=False)
                job.result_image_path = result.get("result_image_path")
                job.total_rooms = result.get("total_rooms", 0)
                job.rooms_with_labels = result.get("rooms_with_labels", 0)
                job.rooms_with_dimensions = result.get("rooms_with_dimensions", 0)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()

    except Exception as e:
        traceback.print_exc()
        _push("failed", 0, 0, str(e)[:200])
        db = SessionLocal()
        try:
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)[:2000]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()
    finally:
        try:
            q.put_nowait({"step": "done", "page": 0, "total": 0, "message": "done"})
        except queue.Full:
            pass
