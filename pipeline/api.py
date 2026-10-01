from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

import cv2

from .config import OCRConfig, ParseConfig, PipelineConfig
from .pipeline import HybridFloorPlanPipeline
from .visualize import draw_final_overlay


def analyze_floorplan_image(
    image_path: str,
    out_json_path: str,
    config: PipelineConfig,
    out_viz_path: Optional[str] = None,
    plan_context: Optional[Dict] = None,
) -> Dict:
    """
    Importable analyzer API for a single floor plan image.
    """
    pipe = HybridFloorPlanPipeline(config)
    output = pipe.analyze_path(image_path, plan_context=plan_context)

    jpath = Path(out_json_path)
    jpath.parent.mkdir(parents=True, exist_ok=True)
    with jpath.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    if out_viz_path:
        image = cv2.imread(image_path)
        if image is not None:
            overlay = draw_final_overlay(image, pipe.last_rooms)
            Path(out_viz_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(out_viz_path, overlay)
    return output
