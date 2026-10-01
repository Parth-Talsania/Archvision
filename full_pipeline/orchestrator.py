from __future__ import annotations

import json
import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2

from pdf_extract import ExtractConfig

from .analyzer_api import analyze_floorplan_image
from .extractor_api import extract_floorplans_from_pdf
from .schemas import AnalyzerConfig, FinalPipelineOutput, FullPipelineOptions, PlanAnalysisResult
from pipeline.frontend_schema import build_frontend_output_multipage, convert_legacy_output_to_frontend


def _setup_logger(log_path: Path, level: str) -> logging.Logger:
    logger = logging.getLogger("full_pipeline")
    logger.handlers.clear()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def _rel(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def _json_safe(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _json_safe(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_json_safe(x) for x in v]
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            return str(v)
    return v


def _augment_polygon_mappings(analysis_json: Dict, bbox: Dict[str, int], dpi: int) -> Dict:
    px_per_pdf_point = float(dpi) / 72.0
    out = dict(analysis_json)
    rooms = out.get("rooms", [])
    mapped_rooms = []
    for room in rooms:
        r = dict(room)
        poly = r.get("polygon_coordinates") or []
        plan_px = [[float(x), float(y)] for x, y in poly]
        page_px = [[float(x) + bbox["x1"], float(y) + bbox["y1"]] for x, y in plan_px]
        pdf_pts = [[x / px_per_pdf_point, y / px_per_pdf_point] for x, y in page_px]
        r["polygon_coordinates_plan_px"] = plan_px
        r["polygon_coordinates_page_px"] = page_px
        r["polygon_coordinates_pdf_points"] = pdf_pts
        mapped_rooms.append(r)
    out["rooms"] = mapped_rooms
    return out


def _worker_analyze(task: Dict[str, Any]) -> Dict[str, Any]:
    out = analyze_floorplan_image(
        image_path=task["image_path"],
        out_json_path=task["out_json_path"],
        config=AnalyzerConfig(**task["analyzer_config"]),
        out_viz_path=task.get("out_viz_path"),
        plan_context=task.get("plan_context"),
    )
    return {"analysis": out}


def _build_frontend_output_from_analysis(
    source_pdf: str,
    plans: List,
    plan_results: List[PlanAnalysisResult],
    plan_analysis_payload: Dict[str, Dict],
    include_debug: bool = False,
) -> Dict[str, Any]:
    """
    Build frontend-ready JSON from analysis results.
    
    Converts existing analysis payloads to the frontend schema format
    with multi-page support.
    """
    from datetime import datetime, timezone
    from pipeline.frontend_schema import SCHEMA_VERSION
    
    pages_data = []
    for r in plan_results:
        if not r.success:
            continue
        
        analysis_data = plan_analysis_payload.get(r.plan_id)
        if not analysis_data:
            continue
        
        # Find the corresponding plan for source info
        plan = next((p for p in plans if p.plan_id == r.plan_id), None)
        if not plan:
            continue
        
        # Convert legacy analysis to frontend format
        frontend_page = convert_legacy_output_to_frontend(
            analysis_data,
            include_debug=include_debug,
        )
        
        # Update page-specific info
        page_data = frontend_page["pages"][0]
        page_data["page_index"] = plan.page_number - 1  # 0-indexed
        page_data["plan_id"] = r.plan_id
        page_data["image_path"] = r.input_image_path
        
        # Update source info
        text_meta = analysis_data.get("text_metadata", {})
        page_data["summary"]["text_strategy"] = text_meta.get("text_source_used", "unknown")
        
        pages_data.append(page_data)
    
    # Sort pages by page_index
    pages_data.sort(key=lambda p: (p.get("page_index", 0), p.get("plan_id", "")))
    
    # Get DPI from first plan
    source_dpi = plans[0].dpi if plans else None
    
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "type": "pdf",
            "file": Path(source_pdf).name,
            "dpi": source_dpi,
            "total_pages": len(pages_data),
        },
        "pages": pages_data,
    }


def run_full_pipeline(
    pdf_path: str,
    out_dir: str,
    extractor_config: ExtractConfig,
    analyzer_config: AnalyzerConfig,
    options: FullPipelineOptions,
) -> str:
    in_pdf = Path(pdf_path)
    if not in_pdf.exists():
        raise FileNotFoundError(f"Input PDF not found: {in_pdf}")

    out_root = Path(out_dir)
    extracted_root = out_root / "extracted_plans"
    plan_results_root = out_root / "plan_results"
    logs_root = out_root / "logs"
    debug_root = Path(analyzer_config.debug_dir).parent if analyzer_config.debug_dir else (out_root / "debug")
    for p in [extracted_root, plan_results_root, logs_root]:
        p.mkdir(parents=True, exist_ok=True)
    if options.save_debug_extractor or analyzer_config.save_debug_analyzer:
        debug_root.mkdir(parents=True, exist_ok=True)

    logger = _setup_logger(logs_root / "run.log", options.log_level)
    logger.info("Starting full pipeline")
    logger.info("PDF: %s", in_pdf)

    # Integration plan:
    # 1) Call extractor API to produce floorplan crops + extraction manifest.
    # 2) Analyze each extracted image via analyzer API into plan_results/.
    # 3) Merge extraction metadata + analysis results into final_output.json.

    extractor_cfg = extractor_config
    extractor_cfg.pdf = str(in_pdf)
    extractor_cfg.out_dir = str(extracted_root)
    if options.save_debug_extractor:
        extractor_cfg.save_debug = True
        extractor_cfg.debug_dir = str(debug_root / "extractor")

    plans, extraction_summary = extract_floorplans_from_pdf(str(in_pdf), str(extracted_root), extractor_cfg)
    analysis_plans = plans
    if options.max_plans is not None:
        analysis_plans = plans[: max(0, int(options.max_plans))]
    logger.info("Extraction complete: %d plan crops (analysis target: %d)", len(plans), len(analysis_plans))

    if len(plans) == 0:
        final = FinalPipelineOutput(
            pipeline={
                "name": "pdf_to_floorplan_analysis",
                "version": "1.0.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "device": analyzer_config.device,
                "configs": {"extractor": _json_safe(asdict(extractor_cfg)), "analyzer": _json_safe(asdict(analyzer_config))},
            },
            input={"source_pdf": str(in_pdf), "page_count": extraction_summary.get("page_count")},
            extraction={"extracted_plan_count": 0, "items": []},
            analysis={"processed_count": 0, "success_count": 0, "failure_count": 0, "items": []},
            results={"plans": [], "totals": {"plans": 0, "rooms": 0}, "error": "No floor plans extracted"},
        )
        out_json = out_root / "final_output.json"
        out_json.write_text(json.dumps(final.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        raise RuntimeError("Extraction produced 0 plans.")

    plan_results: List[PlanAnalysisResult] = []
    plan_analysis_payload: Dict[str, Dict] = {}

    workers = max(1, int(options.workers))
    if analyzer_config.device != "cpu" and workers > 1:
        logger.warning("GPU/auto mode detected; forcing workers=1 to avoid contention.")
        workers = 1

    def _run_one(plan) -> Tuple[PlanAnalysisResult, Optional[Dict]]:
        plan_id = plan.plan_id
        img_path = Path(plan.output_image_path)
        out_json_path = plan_results_root / f"plan_{plan_id}.json"
        out_viz_path = plan_results_root / f"plan_{plan_id}_viz.png"

        if not img_path.exists():
            return (
                PlanAnalysisResult(
                    plan_id=plan_id,
                    input_image_path=str(img_path),
                    analysis_json_path=str(out_json_path),
                    success=False,
                    error="image_not_found",
                ),
                None,
            )
        image = cv2.imread(str(img_path))
        if image is None:
            return (
                PlanAnalysisResult(
                    plan_id=plan_id,
                    input_image_path=str(img_path),
                    analysis_json_path=str(out_json_path),
                    success=False,
                    error="image_unreadable",
                ),
                None,
            )
        h, w = image.shape[:2]
        if min(h, w) < 300:
            return (
                PlanAnalysisResult(
                    plan_id=plan_id,
                    input_image_path=str(img_path),
                    analysis_json_path=str(out_json_path),
                    success=False,
                    error="crop_too_small_for_analysis",
                ),
                None,
            )

        if options.resume and out_json_path.exists():
            try:
                data = json.loads(out_json_path.read_text(encoding="utf-8"))
                return (
                    PlanAnalysisResult(
                        plan_id=plan_id,
                        input_image_path=str(img_path),
                        analysis_json_path=str(out_json_path),
                        success=True,
                        total_rooms=data.get("total_rooms"),
                        viz_path=str(out_viz_path) if out_viz_path.exists() else None,
                    ),
                    data,
                )
            except Exception:
                pass

        per_plan_debug_dir = str((debug_root / "analyzer" / plan_id)) if analyzer_config.save_debug_analyzer else analyzer_config.debug_dir
        cfg = AnalyzerConfig(**{**asdict(analyzer_config), "debug_dir": per_plan_debug_dir})
        plan_context = {
            "pdf_path": str(in_pdf),
            "page_number": int(plan.page_number),
            "crop_bbox_px_page": dict(plan.bbox_px_page),
            "crop_render_dpi": int(plan.dpi),
            "crop_bbox_pdf_points": dict(plan.bbox_pdf_points or {}),
            "analysis_inputs_dir": str(out_root / "analysis_inputs"),
            "plan_id": plan_id,
        }
        data = analyze_floorplan_image(
            image_path=str(img_path),
            out_json_path=str(out_json_path),
            config=cfg,
            out_viz_path=str(out_viz_path),
            plan_context=plan_context,
        )
        return (
            PlanAnalysisResult(
                plan_id=plan_id,
                input_image_path=str(img_path),
                analysis_json_path=str(out_json_path),
                success=True,
                total_rooms=data.get("total_rooms"),
                viz_path=str(out_viz_path),
            ),
            data,
        )

    if workers == 1:
        for plan in analysis_plans:
            logger.info("Analyzing %s", plan.plan_id)
            try:
                plan_id = plan.plan_id
                img_path = Path(plan.output_image_path)
                out_json_path = plan_results_root / f"plan_{plan_id}.json"
                out_viz_path = plan_results_root / f"plan_{plan_id}_viz.png"
                if not img_path.exists():
                    raise FileNotFoundError("image_not_found")
                image = cv2.imread(str(img_path))
                if image is None:
                    raise RuntimeError("image_unreadable")
                if min(image.shape[:2]) < 300:
                    raise RuntimeError("crop_too_small_for_analysis")
                if options.resume and out_json_path.exists():
                    data = json.loads(out_json_path.read_text(encoding="utf-8"))
                else:
                    plan_context = {
                        "pdf_path": str(in_pdf),
                        "page_number": int(plan.page_number),
                        "crop_bbox_px_page": dict(plan.bbox_px_page),
                        "crop_render_dpi": int(plan.dpi),
                        "crop_bbox_pdf_points": dict(plan.bbox_pdf_points or {}),
                        "analysis_inputs_dir": str(out_root / "analysis_inputs"),
                        "plan_id": plan_id,
                    }
                    per_plan_debug_dir = str((debug_root / "analyzer" / plan_id)) if analyzer_config.save_debug_analyzer else analyzer_config.debug_dir
                    cfg = AnalyzerConfig(**{**asdict(analyzer_config), "debug_dir": per_plan_debug_dir})
                    data = analyze_floorplan_image(
                        image_path=str(img_path),
                        out_json_path=str(out_json_path),
                        config=cfg,
                        out_viz_path=str(out_viz_path),
                        plan_context=plan_context,
                    )
                res = PlanAnalysisResult(
                    plan_id=plan_id,
                    input_image_path=str(img_path),
                    analysis_json_path=str(out_json_path),
                    success=True,
                    total_rooms=data.get("total_rooms"),
                    viz_path=str(out_viz_path) if out_viz_path.exists() else None,
                )
                plan_results.append(res)
                plan_analysis_payload[plan_id] = data
            except Exception as e:
                res = PlanAnalysisResult(
                    plan_id=plan.plan_id,
                    input_image_path=plan.output_image_path,
                    analysis_json_path=str(plan_results_root / f"plan_{plan.plan_id}.json"),
                    success=False,
                    error=str(e),
                )
                plan_results.append(res)
                logger.exception("Analysis failed for %s: %s", plan.plan_id, e)
                if options.stop_on_first_failure:
                    break
    else:
        tasks = []
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for plan in analysis_plans:
                plan_id = plan.plan_id
                out_json_path = plan_results_root / f"plan_{plan_id}.json"
                out_viz_path = plan_results_root / f"plan_{plan_id}_viz.png"
                if options.resume and out_json_path.exists():
                    try:
                        data = json.loads(out_json_path.read_text(encoding="utf-8"))
                        plan_results.append(
                            PlanAnalysisResult(
                                plan_id=plan_id,
                                input_image_path=plan.output_image_path,
                                analysis_json_path=str(out_json_path),
                                success=True,
                                total_rooms=data.get("total_rooms"),
                                viz_path=str(out_viz_path) if out_viz_path.exists() else None,
                            )
                        )
                        plan_analysis_payload[plan_id] = data
                        continue
                    except Exception:
                        pass
                fut = ex.submit(
                    _worker_analyze,
                    {
                        "image_path": plan.output_image_path,
                        "out_json_path": str(out_json_path),
                        "out_viz_path": str(out_viz_path),
                        "analyzer_config": asdict(analyzer_config),
                        "plan_context": {
                            "pdf_path": str(in_pdf),
                            "page_number": int(plan.page_number),
                            "crop_bbox_px_page": dict(plan.bbox_px_page),
                            "crop_render_dpi": int(plan.dpi),
                            "crop_bbox_pdf_points": dict(plan.bbox_pdf_points or {}),
                            "analysis_inputs_dir": str(out_root / "analysis_inputs"),
                            "plan_id": plan_id,
                        },
                    },
                )
                tasks.append((plan, fut))
            for plan, fut in tasks:
                try:
                    data = fut.result()["analysis"]
                    plan_results.append(
                        PlanAnalysisResult(
                            plan_id=plan.plan_id,
                            input_image_path=plan.output_image_path,
                            analysis_json_path=str(plan_results_root / f"plan_{plan.plan_id}.json"),
                            success=True,
                            total_rooms=data.get("total_rooms"),
                            viz_path=str(plan_results_root / f"plan_{plan.plan_id}_viz.png"),
                        )
                    )
                    plan_analysis_payload[plan.plan_id] = data
                except Exception as e:
                    plan_results.append(
                        PlanAnalysisResult(
                            plan_id=plan.plan_id,
                            input_image_path=plan.output_image_path,
                            analysis_json_path=str(plan_results_root / f"plan_{plan.plan_id}.json"),
                            success=False,
                            error=str(e),
                        )
                    )
                    logger.exception("Analysis failed for %s: %s", plan.plan_id, e)

    success_count = sum(1 for r in plan_results if r.success)
    failure_count = len(plan_results) - success_count
    total_rooms = 0
    text_source_counts: Dict[str, int] = {}

    extraction_items = []
    for p in plans:
        extraction_items.append(
            {
                "plan_id": p.plan_id,
                "page_number": p.page_number,
                "region_index": p.region_index,
                "dpi": p.dpi,
                "bbox_px_page": p.bbox_px_page,
                "bbox_pdf_points": p.bbox_pdf_points,
                "output_image": _rel(Path(p.output_image_path), out_root),
                "scores": {
                    "page_score": p.page_score,
                    "crop_score": p.crop_score,
                    "validator": p.validator,
                    "yolo_room_count": p.yolo_room_count,
                    "yolo_conf_avg": p.yolo_conf_avg,
                },
            }
        )

    analysis_items = []
    plans_payload = []
    for r in plan_results:
        analysis_items.append(
            {
                "plan_id": r.plan_id,
                "analysis_json": _rel(Path(r.analysis_json_path), out_root),
                "success": r.success,
                "total_rooms": r.total_rooms,
                "error": r.error,
                "text_source_used": (plan_analysis_payload.get(r.plan_id, {}).get("text_metadata", {}) or {}).get("text_source_used"),
                "tokens_total": (plan_analysis_payload.get(r.plan_id, {}).get("text_metadata", {}) or {}).get("tokens_total"),
                "pdf_words_total": (plan_analysis_payload.get(r.plan_id, {}).get("text_metadata", {}) or {}).get("pdf_words_total"),
                "ocr_tokens_total": (plan_analysis_payload.get(r.plan_id, {}).get("text_metadata", {}) or {}).get("ocr_tokens_total"),
                "analysis_image_dpi_used": (plan_analysis_payload.get(r.plan_id, {}).get("text_metadata", {}) or {}).get("analysis_image_dpi_used"),
            }
        )
        src_name = (plan_analysis_payload.get(r.plan_id, {}).get("text_metadata", {}) or {}).get("text_source_used")
        if src_name:
            text_source_counts[src_name] = text_source_counts.get(src_name, 0) + 1
        src = next((x for x in plans if x.plan_id == r.plan_id), None)
        if src is None:
            continue
        analysis_data = plan_analysis_payload.get(r.plan_id)
        if analysis_data and options.export_polygons_page_coords:
            analysis_data = _augment_polygon_mappings(analysis_data, src.bbox_px_page, src.dpi)
        if r.success and analysis_data:
            total_rooms += int(analysis_data.get("total_rooms", 0) or 0)
        plan_entry = {
            "plan_id": r.plan_id,
            "source": {
                "source_pdf": src.source_pdf,
                "page_number": src.page_number,
                "region_index": src.region_index,
                "dpi": src.dpi,
                "bbox_px_page": src.bbox_px_page,
                "bbox_pdf_points": src.bbox_pdf_points,
                "output_image": _rel(Path(src.output_image_path), out_root),
                "coordinate_frames": {
                    "plan_image_px": "polygon coordinates produced by analyzer",
                    "page_image_px": "plan_image_px offset by bbox_px_page.(x1,y1)",
                    "pdf_points": "page_image_px divided by (dpi/72.0)",
                    "px_per_pdf_point": float(src.dpi) / 72.0,
                },
            },
            "text": {
                "text_source_used": (analysis_data or {}).get("text_metadata", {}).get("text_source_used") if analysis_data else None,
                "tokens_total": (analysis_data or {}).get("text_metadata", {}).get("tokens_total") if analysis_data else None,
                "pdf_words_total": (analysis_data or {}).get("text_metadata", {}).get("pdf_words_total") if analysis_data else None,
                "ocr_tokens_total": (analysis_data or {}).get("text_metadata", {}).get("ocr_tokens_total") if analysis_data else None,
                "analysis_image_dpi_used": (analysis_data or {}).get("text_metadata", {}).get("analysis_image_dpi_used") if analysis_data else None,
            },
            "analysis": (
                _json_safe(analysis_data)
                if options.embed_analysis_json and analysis_data is not None
                else {"analysis_json_path": _rel(Path(r.analysis_json_path), out_root), "success": r.success, "error": r.error}
            ),
        }
        plans_payload.append(plan_entry)

    final = FinalPipelineOutput(
        pipeline={
            "name": "pdf_to_floorplan_analysis",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device": analyzer_config.device,
            "configs": {"extractor": _json_safe(asdict(extractor_cfg)), "analyzer": _json_safe(asdict(analyzer_config))},
        },
        input={"source_pdf": str(in_pdf), "page_count": extraction_summary.get("page_count")},
        extraction={"extracted_plan_count": len(plans), "items": extraction_items},
        analysis={
            "processed_count": len(plan_results),
            "success_count": success_count,
            "failure_count": failure_count,
            "text_source_counts": text_source_counts,
            "items": analysis_items,
        },
        results={"plans": plans_payload, "totals": {"plans": len(plans), "rooms": total_rooms}},
    )
    out_json = out_root / "final_output.json"
    out_json.write_text(json.dumps(_json_safe(final.to_dict()), indent=2, ensure_ascii=False), encoding="utf-8")

    # Generate frontend-ready JSON if requested
    frontend_json_path = None
    if options.frontend_format:
        frontend_json_path = out_root / "frontend_output.json"
        frontend_output = _build_frontend_output_from_analysis(
            source_pdf=str(in_pdf),
            plans=plans,
            plan_results=plan_results,
            plan_analysis_payload=plan_analysis_payload,
            include_debug=options.include_debug,
        )
        frontend_json_path.write_text(
            json.dumps(_json_safe(frontend_output), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Frontend JSON saved: %s", frontend_json_path)

    debug_index = {
        "plans": [
            {
                "plan_id": p.plan_id,
                "image": _rel(Path(p.output_image_path), out_root),
                "analysis_json": _rel(Path(plan_results_root / f"plan_{p.plan_id}.json"), out_root),
                "viz": _rel(Path(plan_results_root / f"plan_{p.plan_id}_viz.png"), out_root),
            }
            for p in plans
        ]
    }
    (out_root / "debug" / "index.json").parent.mkdir(parents=True, exist_ok=True)
    (out_root / "debug" / "index.json").write_text(json.dumps(debug_index, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("Completed. extracted=%d success=%d failure=%d", len(plans), success_count, failure_count)
    if len(plans) == 0 or success_count == 0:
        raise RuntimeError("Pipeline failed: extraction or analysis produced no successful outputs.")
    return str(out_json)
