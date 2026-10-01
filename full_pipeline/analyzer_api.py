from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

import cv2

from pipeline import HybridFloorPlanPipeline, OCRConfig, ParseConfig, PipelineConfig
from pipeline.visualize import draw_final_overlay

from .schemas import AnalyzerConfig


def _build_pipeline_config(cfg: AnalyzerConfig, debug_dir: Optional[str] = None) -> PipelineConfig:
    return PipelineConfig(
        model_path=cfg.model_path,
        yolo_img_size=cfg.yolo_img_size,
        yolo_conf=cfg.conf_yolo,
        room_crop_pad=cfg.room_crop_pad,
        ocr_mode=cfg.ocr_mode,
        include_ocr_raw=cfg.include_ocr_raw,
        save_debug=cfg.save_debug_analyzer,
        debug_dir=debug_dir or cfg.debug_dir,
        device=cfg.device,
        text_source=cfg.text_source,
        min_pdf_words=cfg.min_pdf_words,
        save_text_debug=cfg.save_text_debug,
        text_debug_dir=str(Path(debug_dir or cfg.debug_dir) / "text_overlays"),
        ocr=OCRConfig(
            gpu=cfg.use_gpu_ocr,
            upscale=cfg.ocr_scale,
            min_conf_keep=cfg.conf_ocr,
            two_pass_invert=cfg.ocr_two_pass_invert,
            threshold=not cfg.ocr_no_threshold,
            engine=cfg.ocr_engine,
            ocr_dpi=cfg.ocr_dpi,
        ),
        parse=ParseConfig(),
    )


class AnalyzerRunner:
    def __init__(self, config: AnalyzerConfig, debug_dir: Optional[str] = None):
        self.config = config
        pipe_cfg = _build_pipeline_config(config, debug_dir=debug_dir)
        self.pipeline = HybridFloorPlanPipeline(pipe_cfg)

    def analyze(
        self,
        image_path: str,
        out_json_path: str,
        out_viz_path: Optional[str] = None,
        plan_context: Optional[Dict] = None,
    ) -> Dict:
        output = self.pipeline.analyze_path(image_path, plan_context=plan_context)
        jpath = Path(out_json_path)
        jpath.parent.mkdir(parents=True, exist_ok=True)
        with jpath.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        if out_viz_path:
            image = cv2.imread(image_path)
            if image is not None:
                overlay = draw_final_overlay(image, self.pipeline.last_rooms)
                Path(out_viz_path).parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(out_viz_path, overlay)
        return output


def analyze_floorplan_image(
    image_path: str,
    out_json_path: str,
    config: AnalyzerConfig,
    out_viz_path: Optional[str] = None,
    plan_context: Optional[Dict] = None,
) -> Dict:
    runner = AnalyzerRunner(config=config)
    return runner.analyze(image_path=image_path, out_json_path=out_json_path, out_viz_path=out_viz_path, plan_context=plan_context)
