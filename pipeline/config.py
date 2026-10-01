from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple


DEFAULT_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'\"-xX./() ,"


@dataclass
class OCRConfig:
    gpu: bool = False
    allowlist: str = DEFAULT_ALLOWLIST
    upscale: int = 2
    use_clahe: bool = False       # Disabled: CLAHE destroys thin strokes
    threshold: bool = False       # Disabled: binarization kills ', ", -, fractions
    two_pass_invert: bool = False
    line_aspect_ratio_reject: Tuple[float, float] = (0.08, 12.0)
    min_conf_keep: float = 0.2
    engine: str = "easyocr"
    ocr_dpi: int = 600
    adaptive_scale: bool = True
    max_input_dim: int = 800
    watermark_filter: bool = True


@dataclass
class ParseConfig:
    # Synonyms for common EasyOCR misreads on Indian floor plans.
    # Fuzzy matching in parse_semantics handles close variations automatically,
    # so this dict only needs exact-match overrides for tricky cases.
    label_synonyms: Dict[str, str] = field(
        default_factory=lambda: {
            # WC / bathroom variants
            "wc": "Toilet",
            "washroom": "Toilet",
            "bathroom": "Toilet",
            "bath": "Toilet",
            "lav": "Toilet",
            # Hall / Living aliases
            "dining/hall": "Hall",
            "living/hall": "Hall",
            # Common EasyOCR char-swap misreads (e->c, d->cl, etc.)
            "mastcr bcd": "Master Bedroom",
            "mastcr bed": "Master Bedroom",
            "master bcd": "Master Bedroom",
            "mastcr bcd room": "Master Bed Room",
            "master bcd room": "Master Bed Room",
            "mastcr bed room": "Master Bed Room",
            "klaster bed room": "Master Bed Room",
            "klaster bedroom": "Master Bedroom",
            "laster bedroom": "Master Bedroom",
            "laster bed room": "Master Bed Room",
            "master bed": "Master Bedroom",
            "m. bed": "Master Bedroom",
            # Bed room
            "bcd room": "Bed Room",
            "bcdroom": "Bed Room",
            "bcd": "Bed Room",
            # Kitchen
            "kitchcn": "Kitchen",
            "kitchcn / dining": "Kitchen / Dining",
            # Toilet
            "toilct": "Toilet",
            "toilcl": "Toilet",
            "toilt": "Toilet",
            "tollet": "Toilet",
            "toiletoa": "Toilet",
            # Other
            "foue": "Pooja",
            "pooja": "Pooja",
            "poo]a": "Pooja",
            "pooia": "Pooja",
            "jiving": "Living",
            "livlng": "Living",
            "llving": "Living",
            "sit-oul": "Sit-Out",
            "sil-out": "Sit-Out",
            "slt-out": "Sit-Out",
        }
    )
    intersection_ratio_threshold: float = 0.3
    min_label_conf: float = 0.2
    min_dim_conf: float = 0.2


@dataclass
class PipelineConfig:
    model_path: str
    yolo_img_size: int = 640
    yolo_conf: float = 0.35
    yolo_iou: float = 0.5
    polygon_simplify_tol: float = 2.0
    room_crop_pad: int = 20
    overlap_iou_drop_threshold: float = 0.85
    ocr_mode: str = "hybrid"      # Default: full-image first, per-room fallback
    include_ocr_raw: bool = False
    save_debug: bool = False
    debug_dir: str = "results/debug"
    device: str = "auto"
    text_source: str = "auto"
    min_pdf_words: int = 8
    save_text_debug: bool = False
    text_debug_dir: str = "results/debug_text"
    pipeline_version: str = "v3.0.0"
    ocr: OCRConfig = field(default_factory=OCRConfig)
    parse: ParseConfig = field(default_factory=ParseConfig)

    @property
    def debug_path(self) -> Path:
        return Path(self.debug_dir)
