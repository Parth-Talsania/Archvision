"""
Optional wrapper around existing floor_plan_pipeline.py without modifying it.

Usage:
    from char_dimension_module.floor_plan_pipeline_char import CharDimensionFloorPlanAnalyzer

    analyzer = CharDimensionFloorPlanAnalyzer(
        base_model_path="best.pt",
        char_model_path="weights/dim_char_yolov8n.pt",
        use_gpu=True,
    )
    result = analyzer.analyze("plan.png")
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import cv2

from .integration_adapter import enrich_rooms_with_char_dimensions


class CharDimensionFloorPlanAnalyzer:
    def __init__(self, base_model_path: str, char_model_path: str, use_gpu: bool = True):
        # lazy import so this module remains standalone if base pipeline is absent
        from floor_plan_pipeline import FloorPlanAnalyzer  # type: ignore

        self.base = FloorPlanAnalyzer(model_path=base_model_path, use_gpu=use_gpu)
        self.char_model_path = char_model_path
        self.device = "cuda" if use_gpu else "cpu"

    def analyze(self, image_path: str, debug_dir: Optional[str] = None, **kwargs) -> Dict:
        result = self.base.analyze(image_path=image_path, **kwargs)
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Image not readable: {image_path}")

        rooms = result.get("rooms", [])
        enriched = enrich_rooms_with_char_dimensions(
            image=image,
            rooms=rooms,
            char_model_path=self.char_model_path,
            debug_dir=debug_dir,
            device=self.device,
        )
        result["rooms"] = enriched
        result.setdefault("summary", {})["dimension_method"] = "char_detector"
        return result
