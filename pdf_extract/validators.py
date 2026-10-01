from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

try:
    import torch
except Exception:  # pragma: no cover
    torch = None

from ultralytics import YOLO


@dataclass
class ValidationResult:
    accepted: bool
    room_count: int
    conf_avg: float
    reason: str


class YoloFloorplanValidator:
    def __init__(
        self,
        model_path: str,
        min_rooms: int = 3,
        conf: float = 0.25,
        imgsz: int = 640,
        device: str = "auto",
    ):
        p = Path(model_path)
        if not p.exists():
            raise FileNotFoundError(f"YOLO model not found: {p}")
        self.model = YOLO(str(p))
        self.min_rooms = int(min_rooms)
        self.conf = float(conf)
        self.imgsz = int(imgsz)
        self.device = self._resolve_device(device)

    @staticmethod
    def _resolve_device(device: str) -> str:
        dev = (device or "auto").lower()
        cuda_ok = bool(torch and torch.cuda.is_available())
        if dev == "cpu":
            return "cpu"
        if dev == "cuda":
            return "cuda:0" if cuda_ok else "cpu"
        return "cuda:0" if cuda_ok else "cpu"

    def validate(self, crop_bgr: np.ndarray) -> ValidationResult:
        pred = self.model.predict(
            source=crop_bgr,
            conf=self.conf,
            imgsz=self.imgsz,
            iou=0.5,
            device=self.device,
            verbose=False,
        )
        if not pred:
            return ValidationResult(False, 0, 0.0, "no_prediction")
        r = pred[0]
        if r.boxes is None or r.boxes.conf is None:
            return ValidationResult(False, 0, 0.0, "no_boxes")
        confs = r.boxes.conf.cpu().numpy()
        cnt = int(len(confs))
        avg = float(np.mean(confs)) if cnt > 0 else 0.0
        ok = cnt >= self.min_rooms
        return ValidationResult(ok, cnt, avg, "ok" if ok else "too_few_rooms")

