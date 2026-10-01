from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

from pdf_extract import ExtractConfig, PDFFloorPlanExtractor

from .schemas import ExtractedPlan


def _make_plan_id(pdf_stem: str, page_number: int, region_index: int) -> str:
    return f"{pdf_stem}_p{page_number:03d}_r{region_index:02d}"


def extract_floorplans_from_pdf(
    pdf_path: str,
    out_dir: str,
    config: ExtractConfig,
) -> Tuple[List[ExtractedPlan], Dict]:
    """
    Library API wrapper for extractor stage.
    Saves standardized `manifest_extraction.json` in `out_dir`.
    """
    cfg = config
    cfg.pdf = pdf_path
    cfg.out_dir = out_dir
    extractor = PDFFloorPlanExtractor(cfg)
    summary = extractor.run()

    root = Path(out_dir)
    pdf_stem = Path(pdf_path).stem
    plans: List[ExtractedPlan] = []
    for item in summary.get("items", []):
        plan_id = _make_plan_id(pdf_stem, int(item["page_number"]), int(item["region_index"]))
        plans.append(
            # Current flow: extractor emits page-pixel bbox at known dpi. We also store PDF-point bbox for re-render alignment.
            ExtractedPlan(
                plan_id=plan_id,
                source_pdf=str(pdf_path),
                pdf_stem=pdf_stem,
                page_number=int(item["page_number"]),
                region_index=int(item["region_index"]),
                dpi=int(cfg.dpi),
                bbox_px_page={
                    "x1": int(item["bbox_px"]["x1"]),
                    "y1": int(item["bbox_px"]["y1"]),
                    "x2": int(item["bbox_px"]["x2"]),
                    "y2": int(item["bbox_px"]["y2"]),
                },
                bbox_pdf_points={
                    "x1": float(item["bbox_px"]["x1"]) / (float(cfg.dpi) / 72.0),
                    "y1": float(item["bbox_px"]["y1"]) / (float(cfg.dpi) / 72.0),
                    "x2": float(item["bbox_px"]["x2"]) / (float(cfg.dpi) / 72.0),
                    "y2": float(item["bbox_px"]["y2"]) / (float(cfg.dpi) / 72.0),
                },
                output_image_path=str(root / item["output_image"]),
                page_score=item.get("page_score"),
                crop_score=item.get("crop_score"),
                validator=item.get("validator"),
                yolo_room_count=item.get("yolo_room_count"),
                yolo_conf_avg=item.get("yolo_conf_avg"),
                width_px=item.get("width"),
                height_px=item.get("height"),
            )
        )

    std_manifest = {
        "pdf": str(pdf_path),
        "page_count": summary.get("page_count"),
        "processed_pages": summary.get("processed_pages"),
        "extracted_plan_count": len(plans),
        "items": [asdict(p) for p in plans],
        "raw_extractor_summary": summary,
    }
    out_manifest = root / "manifest_extraction.json"
    with out_manifest.open("w", encoding="utf-8") as f:
        json.dump(std_manifest, f, indent=2, ensure_ascii=False)
    return plans, summary
