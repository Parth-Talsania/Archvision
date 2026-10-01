from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ExtractedPlan:
    plan_id: str
    source_pdf: str
    pdf_stem: str
    page_number: int
    region_index: int
    dpi: int
    bbox_px_page: Dict[str, int]
    output_image_path: str
    bbox_pdf_points: Optional[Dict[str, float]] = None
    page_score: Optional[float] = None
    crop_score: Optional[float] = None
    validator: Optional[str] = None
    yolo_room_count: Optional[int] = None
    yolo_conf_avg: Optional[float] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None


@dataclass
class PlanAnalysisResult:
    plan_id: str
    input_image_path: str
    analysis_json_path: str
    success: bool
    error: Optional[str] = None
    total_rooms: Optional[int] = None
    viz_path: Optional[str] = None


@dataclass
class AnalyzerConfig:
    model_path: str
    device: str = "auto"
    use_gpu_ocr: bool = False
    yolo_img_size: int = 640
    conf_yolo: float = 0.35
    conf_ocr: float = 0.2
    room_crop_pad: int = 20
    ocr_mode: str = "per_room"
    ocr_scale: int = 3
    ocr_two_pass_invert: bool = False
    ocr_no_threshold: bool = False
    include_ocr_raw: bool = False
    save_debug_analyzer: bool = False
    debug_dir: str = ""
    text_source: str = "auto"
    ocr_engine: str = "paddle"
    ocr_dpi: int = 600
    min_pdf_words: int = 8
    save_text_debug: bool = False


@dataclass
class FullPipelineOptions:
    resume: bool = False
    embed_analysis_json: bool = False
    stop_on_first_failure: bool = False
    max_plans: Optional[int] = None
    workers: int = 1
    log_level: str = "INFO"
    export_polygons_page_coords: bool = False
    save_debug_extractor: bool = False
    frontend_format: bool = False  # Whether to emit frontend-ready JSON
    include_debug: bool = False  # Include debug payload in frontend output


@dataclass
class FinalPipelineOutput:
    pipeline: Dict[str, Any]
    input: Dict[str, Any]
    extraction: Dict[str, Any]
    analysis: Dict[str, Any]
    results: Dict[str, Any]

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
