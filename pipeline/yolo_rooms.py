from __future__ import annotations

import logging
from typing import List

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from .config import PipelineConfig
from .geometry import bbox_from_polygon, mask_to_polygon, polygon_iou
from .types import RoomInstance


LOGGER = logging.getLogger(__name__)


class YoloRoomDetector:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.model = YOLO(config.model_path)
        self.predict_device = self._resolve_predict_device(config.device)
        LOGGER.info("YOLO predict device: %s", self.predict_device)

    @staticmethod
    def _resolve_predict_device(device_cfg: str) -> str:
        cfg = (device_cfg or "auto").lower()
        cuda_ok = torch.cuda.is_available()
        if cfg == "cpu":
            return "cpu"
        if cfg == "cuda":
            return "cuda:0" if cuda_ok else "cpu"
        # auto
        return "cuda:0" if cuda_ok else "cpu"

    def detect(self, image: np.ndarray) -> List[RoomInstance]:
        results = self.model.predict(
            source=image,
            conf=self.config.yolo_conf,
            iou=self.config.yolo_iou,
            imgsz=self.config.yolo_img_size,
            device=self.predict_device,
            verbose=False,
        )
        if not results:
            return []
        result = results[0]
        if result.masks is None or result.masks.data is None:
            return []

        room_instances: List[RoomInstance] = []
        cls_names = result.names if hasattr(result, "names") else {}

        masks = result.masks.data.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy() if result.boxes is not None else np.ones(len(masks), dtype=float)
        classes = result.boxes.cls.cpu().numpy().astype(int) if result.boxes is not None else np.zeros(len(masks), dtype=int)
        h, w = image.shape[:2]

        for idx, (mask, conf, cls_id) in enumerate(zip(masks, confs, classes), start=1):
            # Ultralytics masks are in model shape; resize to original.
            mask_resized = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
            poly = mask_to_polygon(mask_resized)
            if poly is None:
                continue
            poly_s = poly.simplify(self.config.polygon_simplify_tol, preserve_topology=True)
            if not poly_s.is_valid:
                poly_s = poly_s.buffer(0)
            if poly_s.is_empty:
                continue

            bbox = bbox_from_polygon(poly_s)
            centroid = (float(poly_s.centroid.x), float(poly_s.centroid.y))
            class_name = str(cls_names.get(int(cls_id), "room")).replace("_", " ")
            room_instances.append(
                RoomInstance(
                    id=idx,
                    yolo_conf=float(conf),
                    mask=(mask_resized > 0.5).astype(np.uint8),
                    polygon=poly,
                    polygon_simplified=poly_s,
                    bbox=bbox,
                    centroid=centroid,
                    area_px2=float(poly_s.area),
                    class_name=class_name,
                )
            )

        return self._dedupe_by_iou(room_instances)

    def _dedupe_by_iou(self, rooms: List[RoomInstance]) -> List[RoomInstance]:
        if not rooms:
            return rooms
        keep: List[RoomInstance] = []
        for room in sorted(rooms, key=lambda r: r.yolo_conf, reverse=True):
            is_dup = False
            for kept in keep:
                iou = polygon_iou(room.polygon_simplified, kept.polygon_simplified)
                inter = room.polygon_simplified.intersection(kept.polygon_simplified).area
                min_area = max(1e-6, min(room.polygon_simplified.area, kept.polygon_simplified.area))
                contain_ratio = inter / min_area
                if iou > self.config.overlap_iou_drop_threshold or contain_ratio > 0.9:
                    is_dup = True
                    LOGGER.debug(
                        "Dropped overlap room %s due to IoU %.3f / contain %.3f with room %s",
                        room.id,
                        iou,
                        contain_ratio,
                        kept.id,
                    )
                    break
            if not is_dup:
                keep.append(room)
        for new_id, room in enumerate(keep, start=1):
            room.id = new_id
        return keep
