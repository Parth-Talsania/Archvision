import json
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

import cv2
import numpy as np
from ultralytics import YOLO

try:
    import fitz  # PyMuPDF
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise ImportError(
        "PyMuPDF is required for Step-1 PDF extraction. Install with: pip install pymupdf"
    ) from exc


@dataclass
class PageScore:
    page_index: int
    score: float
    edge_density: float
    hv_line_count: int
    hv_long_count: int
    saturation_mean: float
    black_ratio: float
    selected: bool = False
    image_path: Optional[str] = None


@dataclass
class DetectionDecision:
    page_index: int
    det_index: int
    class_id: int
    class_name: str
    confidence: float
    area_ratio: float
    bbox: Tuple[int, int, int, int]
    kept: bool
    reason: str
    output_filename: Optional[str] = None


class BrochureFloorPlanExtractor:
    """
    Step-1 extractor:
      1. Render brochure PDF pages at high resolution
      2. Score each page for floor-plan likelihood
      3. Export selected page images for Step-2 (YOLO + OCR)
    """

    def __init__(
        self,
        yolo_model_path: Optional[Union[str, Path]] = None,
        dpi: int = 300,
        min_score: float = 0.35,
        top_k: Optional[int] = 3,
        trim_border: bool = True,
        yolo_conf: float = 0.25,
        yolo_iou: float = 0.5,
        yolo_imgsz: int = 1024,
        min_area_ratio: float = 0.03,
        top_k_per_page: int = 2,
        crop_padding: int = 10,
        floorplan_class_ids: Optional[List[int]] = None,
        save_debug: bool = True,
        device: str = "auto",
        min_det_area_ratio: float = 0.001,
        min_component_detections: int = 4,
        component_close_kernel: int = 31,
    ):
        self.yolo_model_path = None if yolo_model_path is None else Path(yolo_model_path)
        self.dpi = dpi
        self.min_score = min_score
        self.top_k = top_k
        self.trim_border = trim_border
        self.yolo_conf = yolo_conf
        self.yolo_iou = yolo_iou
        self.yolo_imgsz = yolo_imgsz
        self.min_area_ratio = min_area_ratio
        self.top_k_per_page = max(1, int(top_k_per_page))
        self.crop_padding = max(0, int(crop_padding))
        self.floorplan_class_ids = set(floorplan_class_ids) if floorplan_class_ids else None
        self.save_debug = save_debug
        self.device = self._resolve_device(device)
        self.min_det_area_ratio = min_det_area_ratio
        self.min_component_detections = max(1, int(min_component_detections))
        self.component_close_kernel = max(3, int(component_close_kernel) | 1)
        self.model: Optional[YOLO] = None
        if self.yolo_model_path is not None:
            if not self.yolo_model_path.exists():
                raise FileNotFoundError(f"YOLO model not found: {self.yolo_model_path}")
            self.model = YOLO(str(self.yolo_model_path))

    @staticmethod
    def _resolve_device(device: str) -> str:
        dev = (device or "auto").lower()
        try:
            import torch

            cuda_ok = torch.cuda.is_available()
        except Exception:
            cuda_ok = False
        if dev == "cpu":
            return "cpu"
        if dev == "cuda":
            return "cuda:0" if cuda_ok else "cpu"
        return "cuda:0" if cuda_ok else "cpu"

    def _render_page(self, page: "fitz.Page") -> np.ndarray:
        scale = self.dpi / 72.0
        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    def _trim_white_border(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        non_white = gray < 245
        if not np.any(non_white):
            return image
        ys, xs = np.where(non_white)
        y1, y2 = int(ys.min()), int(ys.max())
        x1, x2 = int(xs.min()), int(xs.max())
        pad = 10
        y1 = max(0, y1 - pad)
        x1 = max(0, x1 - pad)
        y2 = min(image.shape[0] - 1, y2 + pad)
        x2 = min(image.shape[1] - 1, x2 + pad)
        return image[y1 : y2 + 1, x1 : x2 + 1]

    def _infer_floorplan_class_ids(self, names: Dict[int, str]) -> Set[int]:
        if self.floorplan_class_ids is not None:
            return set(int(x) for x in self.floorplan_class_ids)
        if len(names) <= 1:
            return set(names.keys()) if names else {0}
        out: Set[int] = set()
        for cid, cname in names.items():
            n = str(cname).lower()
            if any(k in n for k in ["room", "floor", "plan", "layout", "flat", "unit"]):
                out.add(int(cid))
        if not out:
            out = set(names.keys())
        return out

    @staticmethod
    def _looks_like_room_model(names: Dict[int, str]) -> bool:
        if not names:
            return False
        room_tokens = ["bed", "hall", "toilet", "kitchen", "pooja", "utility", "sit_out", "balcony", "room"]
        hits = 0
        for _, cname in names.items():
            n = str(cname).lower()
            if any(t in n for t in room_tokens):
                hits += 1
        return hits >= max(2, len(names) // 2)

    def _render_mask_from_polygon(self, h: int, w: int, poly_xy: np.ndarray) -> np.ndarray:
        mask = np.zeros((h, w), dtype=np.uint8)
        if poly_xy is None or len(poly_xy) < 3:
            return mask
        pts = np.round(poly_xy).astype(np.int32)
        pts[:, 0] = np.clip(pts[:, 0], 0, w - 1)
        pts[:, 1] = np.clip(pts[:, 1], 0, h - 1)
        cv2.fillPoly(mask, [pts], 255)
        return mask

    def _tight_crop_masked(self, image: np.ndarray, mask: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        ys, xs = np.where(mask > 0)
        if len(xs) == 0 or len(ys) == 0:
            return image.copy(), (0, 0, image.shape[1] - 1, image.shape[0] - 1)
        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        x1 = max(0, x1 - self.crop_padding)
        y1 = max(0, y1 - self.crop_padding)
        x2 = min(image.shape[1] - 1, x2 + self.crop_padding)
        y2 = min(image.shape[0] - 1, y2 + self.crop_padding)

        crop = image[y1 : y2 + 1, x1 : x2 + 1].copy()
        crop_mask = mask[y1 : y2 + 1, x1 : x2 + 1]
        # Keep only plan pixels; transparent background in PNG.
        rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
        rgba[:, :, 3] = crop_mask
        return rgba, (x1, y1, x2, y2)

    def _save_debug_overlay(
        self,
        image: np.ndarray,
        page_index: int,
        decisions: List[DetectionDecision],
        output_dir: Path,
    ) -> Optional[str]:
        if not self.save_debug:
            return None
        overlay = image.copy()
        for d in decisions:
            x1, y1, x2, y2 = d.bbox
            color = (0, 220, 0) if d.kept else (0, 0, 255)
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
            text = f"{d.class_name} c={d.confidence:.2f} a={d.area_ratio:.3f} {d.reason}"
            cv2.putText(
                overlay,
                text[:100],
                (x1, max(20, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )
        dbg_dir = output_dir / "debug_overlays"
        dbg_dir.mkdir(parents=True, exist_ok=True)
        dbg_path = dbg_dir / f"page_{page_index + 1:03d}_overlay.png"
        cv2.imwrite(str(dbg_path), overlay)
        return str(dbg_path)

    def _extract_components_from_candidate_masks(
        self,
        candidate_masks: List[np.ndarray],
        page_h: int,
        page_w: int,
    ) -> List[np.ndarray]:
        if not candidate_masks:
            return []
        union_mask = np.zeros((page_h, page_w), dtype=np.uint8)
        for m in candidate_masks:
            union_mask = cv2.bitwise_or(union_mask, (m > 0).astype(np.uint8) * 255)

        # Bridge small wall gaps so adjacent room masks become one plan component.
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (self.component_close_kernel, self.component_close_kernel))
        union_mask = cv2.morphologyEx(union_mask, cv2.MORPH_CLOSE, k, iterations=1)
        union_mask = cv2.morphologyEx(union_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(union_mask, connectivity=8)
        comps: List[np.ndarray] = []
        for lid in range(1, num_labels):
            comp = np.zeros_like(union_mask, dtype=np.uint8)
            comp[labels == lid] = 255
            comps.append(comp)
        return comps

    def _page_features(self, image: np.ndarray) -> Tuple[Dict[str, float], float]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        edges = cv2.Canny(gray, threshold1=70, threshold2=160)
        edge_density = float(np.mean(edges > 0))

        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=120,
            minLineLength=int(min(image.shape[:2]) * 0.08),
            maxLineGap=8,
        )

        hv_count = 0
        hv_long_count = 0
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dx > 3 * dy or dy > 3 * dx:
                    hv_count += 1
                    length = float(np.hypot(dx, dy))
                    if length >= 0.15 * min(image.shape[:2]):
                        hv_long_count += 1

        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        black_ratio = float(np.mean(bw > 0))
        saturation_mean = float(np.mean(hsv[:, :, 1]))

        edge_score = np.clip(edge_density / 0.10, 0.0, 1.0)
        line_score = np.clip(hv_count / 260.0, 0.0, 1.0)
        line_quality = hv_long_count / max(1.0, hv_count)
        line_quality_score = np.clip((line_quality - 0.12) / 0.20, 0.0, 1.0)
        low_sat_score = 1.0 - np.clip(saturation_mean / 100.0, 0.0, 1.0)
        # Prefer moderate ink coverage. Extremely dark pages are often non-floorplan brochure sections.
        if black_ratio < 0.015:
            ink_score = 0.0
        elif black_ratio <= 0.45:
            ink_score = np.clip(black_ratio / 0.18, 0.0, 1.0)
        elif black_ratio <= 0.75:
            ink_score = np.clip(1.0 - ((black_ratio - 0.45) / 0.30) * 0.7, 0.0, 1.0)
        else:
            ink_score = np.clip(0.15 - (black_ratio - 0.75) * 1.5, 0.0, 1.0)
        photo_penalty = np.clip((saturation_mean - 45.0) / 80.0, 0.0, 1.0)
        dark_penalty = np.clip((black_ratio - 0.75) / 0.20, 0.0, 1.0)

        score = (
            0.36 * edge_score
            + 0.30 * line_score
            + 0.16 * line_quality_score
            + 0.10 * low_sat_score
            + 0.08 * ink_score
            - 0.20 * photo_penalty
            - 0.18 * dark_penalty
        )
        score = float(np.clip(score, 0.0, 1.0))

        features = {
            "edge_density": edge_density,
            "hv_line_count": float(hv_count),
            "hv_long_count": float(hv_long_count),
            "saturation_mean": saturation_mean,
            "black_ratio": black_ratio,
        }
        return features, score

    def extract_floorplan_pages(
        self,
        pdf_path: Union[str, Path],
        output_dir: Union[str, Path],
    ) -> Dict:
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        page_scores: List[PageScore] = []
        rendered_pages: List[np.ndarray] = []
        all_decisions: List[DetectionDecision] = []

        for page_index in range(len(doc)):
            page = doc[page_index]
            img = self._render_page(page)
            if self.trim_border:
                img = self._trim_white_border(img)
            rendered_pages.append(img)

            features, score = self._page_features(img)
            page_scores.append(
                PageScore(
                    page_index=page_index,
                    score=score,
                    edge_density=features["edge_density"],
                    hv_line_count=int(features["hv_line_count"]),
                    hv_long_count=int(features["hv_long_count"]),
                    saturation_mean=features["saturation_mean"],
                    black_ratio=features["black_ratio"],
                )
            )

        exported_images: List[str] = []
        page_debug_map: Dict[int, str] = {}
        if self.model is None:
            ranked_indices = sorted(range(len(page_scores)), key=lambda i: page_scores[i].score, reverse=True)
            selected_indices = [i for i in ranked_indices if page_scores[i].score >= self.min_score]
            if self.top_k is not None:
                selected_indices = selected_indices[: self.top_k]
            selected_set = set(selected_indices)
            for i, ps in enumerate(page_scores):
                if i not in selected_set:
                    continue
                ps.selected = True
                out_name = f"floorplan_page_{ps.page_index + 1:03d}_score_{ps.score:.3f}.png"
                out_path = output_dir / out_name
                cv2.imwrite(str(out_path), rendered_pages[i])
                ps.image_path = str(out_path)
                exported_images.append(str(out_path))
        else:
            sample = self.model.predict(source=rendered_pages[0], conf=self.yolo_conf, iou=self.yolo_iou, imgsz=self.yolo_imgsz, device=self.device, verbose=False)
            names = sample[0].names if sample else {0: "floorplan"}
            room_model_mode = self._looks_like_room_model(names)
            allowed_ids = set(names.keys()) if room_model_mode else self._infer_floorplan_class_ids(names)
            for i, page_img in enumerate(rendered_pages):
                h, w = page_img.shape[:2]
                result = self.model.predict(
                    source=page_img,
                    conf=self.yolo_conf,
                    iou=self.yolo_iou,
                    imgsz=self.yolo_imgsz,
                    device=self.device,
                    retina_masks=True,
                    verbose=False,
                )[0]
                page_decisions: List[DetectionDecision] = []
                valid: List[Tuple[float, np.ndarray, DetectionDecision]] = []
                if result.masks is not None and result.masks.xy is not None and result.boxes is not None:
                    confs = result.boxes.conf.cpu().numpy()
                    clss = result.boxes.cls.cpu().numpy().astype(int)
                    polys = result.masks.xy
                    for di, (poly, conf, cls_id) in enumerate(zip(polys, confs, clss), start=1):
                        cls_name = str(names.get(int(cls_id), str(cls_id)))
                        if int(cls_id) not in allowed_ids:
                            d = DetectionDecision(i, di, int(cls_id), cls_name, float(conf), 0.0, (0, 0, 0, 0), False, "class_filtered")
                            page_decisions.append(d)
                            continue
                        mask = self._render_mask_from_polygon(h, w, poly)
                        area = float(np.count_nonzero(mask))
                        area_ratio = area / float(h * w)
                        ys, xs = np.where(mask > 0)
                        if len(xs) == 0:
                            d = DetectionDecision(i, di, int(cls_id), cls_name, float(conf), area_ratio, (0, 0, 0, 0), False, "empty_mask")
                            page_decisions.append(d)
                            continue
                        bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
                        # In room-model mode, single room masks are small; use separate lower threshold.
                        min_det_ratio = self.min_det_area_ratio if room_model_mode else self.min_area_ratio
                        if area_ratio < min_det_ratio:
                            d = DetectionDecision(i, di, int(cls_id), cls_name, float(conf), area_ratio, bbox, False, "area_too_small")
                            page_decisions.append(d)
                            continue
                        d = DetectionDecision(i, di, int(cls_id), cls_name, float(conf), area_ratio, bbox, True, "kept_candidate")
                        page_decisions.append(d)
                        valid.append((area, mask, d))
                kept_components: List[Tuple[float, np.ndarray, float]] = []
                if room_model_mode:
                    candidate_masks = [m for _, m, _ in valid]
                    comps = self._extract_components_from_candidate_masks(candidate_masks, h, w)
                    for comp_mask in comps:
                        comp_area = float(np.count_nonzero(comp_mask))
                        comp_ratio = comp_area / float(h * w)
                        if comp_ratio < self.min_area_ratio:
                            continue
                        # Count how many detections support this component.
                        support = 0
                        for _, m, _ in valid:
                            inter = float(np.count_nonzero((m > 0) & (comp_mask > 0)))
                            if inter > 0:
                                support += 1
                        if support < self.min_component_detections:
                            continue
                        kept_components.append((comp_area, comp_mask, float(support)))
                    kept_components = sorted(kept_components, key=lambda x: x[0], reverse=True)[: self.top_k_per_page]
                    if kept_components:
                        page_scores[i].selected = True
                    # Mark raw detections as kept only if they overlap a kept component.
                    kept_comp_masks = [kc[1] for kc in kept_components]
                    for _, m, d in valid:
                        overlap = any(np.count_nonzero((m > 0) & (cm > 0)) > 0 for cm in kept_comp_masks)
                        if not overlap:
                            d.kept = False
                            d.reason = "component_rejected"
                        else:
                            d.reason = "kept_component_member"
                    for rank, (comp_area, comp_mask, support) in enumerate(kept_components, start=1):
                        crop_rgba, _ = self._tight_crop_masked(page_img, comp_mask)
                        comp_ratio = comp_area / float(h * w)
                        out_name = (
                            f"floorplan_page_{i + 1:03d}_comp_{rank:02d}"
                            f"_support_{int(support)}_area_{comp_ratio:.3f}.png"
                        )
                        out_path = output_dir / out_name
                        cv2.imwrite(str(out_path), crop_rgba)
                        exported_images.append(str(out_path))
                else:
                    # Keep only top-K largest masks for this page.
                    valid = sorted(valid, key=lambda x: x[0], reverse=True)[: self.top_k_per_page]
                    kept_ids = {id(v[2]) for v in valid}
                    for d in page_decisions:
                        if d.kept and id(d) not in kept_ids:
                            d.kept = False
                            d.reason = "dropped_topk"
                    if valid:
                        page_scores[i].selected = True
                    for rank, (_, mask, dec) in enumerate(valid, start=1):
                        crop_rgba, _ = self._tight_crop_masked(page_img, mask)
                        out_name = (
                            f"floorplan_page_{i + 1:03d}_det_{rank:02d}"
                            f"_conf_{dec.confidence:.3f}_area_{dec.area_ratio:.3f}.png"
                        )
                        out_path = output_dir / out_name
                        cv2.imwrite(str(out_path), crop_rgba)
                        dec.output_filename = str(out_path)
                        dec.reason = "kept"
                        exported_images.append(str(out_path))
                page_debug = self._save_debug_overlay(page_img, i, page_decisions, output_dir)
                if page_debug:
                    page_debug_map[i] = page_debug
                all_decisions.extend(page_decisions)

        # Deterministic ordering.
        exported_images = sorted(exported_images)
        for ps in page_scores:
            if ps.selected:
                # First output on that page if any.
                page_prefix = f"floorplan_page_{ps.page_index + 1:03d}_"
                matches = [p for p in exported_images if Path(p).name.startswith(page_prefix)]
                if matches:
                    ps.image_path = matches[0]

        manifest = {
            "pdf_path": str(pdf_path),
            "total_pages": len(page_scores),
            "yolo_model_path": None if self.yolo_model_path is None else str(self.yolo_model_path),
            "yolo_conf": self.yolo_conf,
            "yolo_iou": self.yolo_iou,
            "yolo_imgsz": self.yolo_imgsz,
            "min_area_ratio": self.min_area_ratio,
            "top_k_per_page": self.top_k_per_page,
            "dpi": self.dpi,
            "min_score": self.min_score,
            "top_k": self.top_k,
            "selected_images": exported_images,
            "page_scores": [
                {
                    "page_index": ps.page_index,
                    "score": round(ps.score, 4),
                    "edge_density": round(ps.edge_density, 6),
                    "hv_line_count": ps.hv_line_count,
                    "hv_long_count": ps.hv_long_count,
                    "saturation_mean": round(ps.saturation_mean, 3),
                    "black_ratio": round(ps.black_ratio, 6),
                    "selected": ps.selected,
                    "image_path": ps.image_path,
                    "debug_overlay": page_debug_map.get(ps.page_index),
                }
                for ps in page_scores
            ],
            "decisions": [
                {
                    "page_index": d.page_index,
                    "det_index": d.det_index,
                    "class_id": d.class_id,
                    "class_name": d.class_name,
                    "confidence": round(d.confidence, 5),
                    "area_ratio": round(d.area_ratio, 6),
                    "bbox": list(d.bbox),
                    "kept": d.kept,
                    "reason": d.reason,
                    "output_filename": d.output_filename,
                }
                for d in all_decisions
            ],
        }

        manifest_path = output_dir / "step1_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        decisions_csv = output_dir / "step1_decisions.csv"
        with open(decisions_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "page_index",
                    "det_index",
                    "class_id",
                    "class_name",
                    "confidence",
                    "area_ratio",
                    "bbox_x1",
                    "bbox_y1",
                    "bbox_x2",
                    "bbox_y2",
                    "kept",
                    "reason",
                    "output_filename",
                ]
            )
            for d in all_decisions:
                writer.writerow(
                    [
                        d.page_index,
                        d.det_index,
                        d.class_id,
                        d.class_name,
                        f"{d.confidence:.6f}",
                        f"{d.area_ratio:.6f}",
                        d.bbox[0],
                        d.bbox[1],
                        d.bbox[2],
                        d.bbox[3],
                        int(d.kept),
                        d.reason,
                        d.output_filename or "",
                    ]
                )

        return manifest
