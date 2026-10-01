from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import torch
from shapely.geometry import Point

from .config import PipelineConfig
from .geometry import CropTransform, extract_room_crop, mask_outside_polygon, polygon_global_to_local
from .ocr_engine import OCREngine, preprocess_for_ocr
from .ocr_merge import filter_watermark_tokens, merge_room_tokens
from .output_schema import build_output
from .frontend_schema import build_frontend_output
from .paddle_engine import run_paddleocr
from .parse_semantics import best_dimension, parse_area, parse_dimensions, parse_dimensions_candidates, pick_label
from .pdf_text import extract_pdf_tokens_for_crop, render_pdf_crop
from .types import OCRToken, RoomInstance
from .visualize import draw_final_overlay, draw_ocr_overlay, save_debug_image
from .yolo_rooms import YoloRoomDetector


LOGGER = logging.getLogger(__name__)


class HybridFloorPlanPipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.detector = YoloRoomDetector(config)
        use_gpu = self._resolve_ocr_gpu(config)
        ocr_cfg = replace(config.ocr, gpu=use_gpu)
        self.ocr_engine = OCREngine(ocr_cfg, languages=["en"])
        LOGGER.info("OCR GPU enabled: %s", use_gpu)
        self.last_rooms: List[RoomInstance] = []

    @staticmethod
    def _resolve_ocr_gpu(config: PipelineConfig) -> bool:
        cuda_ok = torch.cuda.is_available()
        if config.device == "cpu":
            return False
        if config.ocr.gpu and cuda_ok:
            return True
        return False

    def analyze_path(self, image_path: str, plan_context: Optional[Dict[str, Any]] = None) -> Dict:
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Image not found or unreadable: {image_path}")
        return self.analyze(image=image, image_path=image_path, plan_context=plan_context)

    def analyze(self, image: np.ndarray, image_path: str = "in_memory.png", plan_context: Optional[Dict[str, Any]] = None) -> Dict:
        # Keep clean image for all OCR operations.
        yolo_input = image.copy()
        ocr_input = image.copy()
        context = plan_context or {}
        text_meta = {
            "text_source_used": "unknown",
            "tokens_total": 0,
            "pdf_words_total": 0,
            "ocr_tokens_total": 0,
            "analysis_image_dpi_used": context.get("crop_render_dpi"),
        }

        # Pipeline flow insertion point:
        # PDF crop context -> choose text source layer (pdf_text preferred, OCR fallback) -> map tokens to rooms.
        # Non-PDF standalone image keeps existing OCR behavior for backward compatibility.
        if self._has_pdf_context(context):
            tokens, text_meta, analysis_image = self._get_text_tokens_with_context(ocr_input, context, image_stem=Path(image_path).stem)
            yolo_input = analysis_image.copy()
            rooms = self.detector.detect(yolo_input)
            room_to_tokens = self._associate_tokens_to_rooms(tokens, rooms)
            for room in rooms:
                room.ocr_tokens = room_to_tokens.get(room.id, [])
                self._finalize_room_semantics(room)
        else:
            rooms = self.detector.detect(yolo_input)
            if self.config.ocr_mode == "full_image":
                all_tokens = self.ocr_engine.run_easyocr(ocr_input)
                room_to_tokens = self._associate_tokens_to_rooms(all_tokens, rooms)
                for room in rooms:
                    room.ocr_tokens = room_to_tokens.get(room.id, [])
                    self._finalize_room_semantics(room)
                text_meta["text_source_used"] = "easyocr"
                text_meta["tokens_total"] = len(all_tokens)
                text_meta["ocr_tokens_total"] = len(all_tokens)
            elif self.config.ocr_mode == "hybrid":
                self._run_hybrid_ocr(ocr_input, rooms, image_name=Path(image_path).stem)
                self._propagate_related_room_dimensions(rooms)
                total = sum(len(r.ocr_tokens) for r in rooms)
                text_meta["text_source_used"] = "hybrid"
                text_meta["tokens_total"] = total
                text_meta["ocr_tokens_total"] = total
            else:
                self._run_per_room_ocr(ocr_input, rooms, image_name=Path(image_path).stem)
                self._fill_missing_dimensions_from_full_image(ocr_input, rooms)
                self._propagate_related_room_dimensions(rooms)
                total = sum(len(r.ocr_tokens) for r in rooms)
                text_meta["text_source_used"] = "easyocr"
                text_meta["tokens_total"] = total
                text_meta["ocr_tokens_total"] = total

        output = build_output(
            image_path=image_path,
            image=yolo_input,
            rooms=rooms,
            config=self.config,
            include_text_debug=self.config.save_debug or self.config.include_ocr_raw,
            text_meta=text_meta,
        )
        self.last_rooms = rooms
        return output

    def _has_pdf_context(self, context: Dict[str, Any]) -> bool:
        return bool(context.get("pdf_path") and context.get("page_number") and context.get("crop_bbox_px_page"))

    def _context_bbox_pdf_points(self, context: Dict[str, Any]) -> Optional[tuple]:
        bbox_pdf = context.get("crop_bbox_pdf_points")
        if bbox_pdf:
            if isinstance(bbox_pdf, dict):
                return (
                    float(bbox_pdf["x1"]),
                    float(bbox_pdf["y1"]),
                    float(bbox_pdf["x2"]),
                    float(bbox_pdf["y2"]),
                )
            if isinstance(bbox_pdf, (list, tuple)) and len(bbox_pdf) == 4:
                return tuple(float(v) for v in bbox_pdf)
            raise ValueError("crop_bbox_pdf_points must be dict{x1,y1,x2,y2} or 4-item tuple/list")
        bbox = context.get("crop_bbox_px_page")
        dpi = float(context.get("crop_render_dpi") or 0)
        if not bbox or dpi <= 0:
            return None
        s = dpi / 72.0
        return (bbox["x1"] / s, bbox["y1"] / s, bbox["x2"] / s, bbox["y2"] / s)

    def _run_ocr_fallback(self, image_bgr: np.ndarray) -> tuple[list[OCRToken], str]:
        # Primary fallback engine: PaddleOCR (if available), then EasyOCR.
        processed, _ = preprocess_for_ocr(image_bgr, self.config.ocr)
        proc_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR) if processed.ndim == 2 else processed
        tokens: List[OCRToken] = []
        source_used = "easyocr"
        if self.config.ocr.engine == "paddle":
            tokens = run_paddleocr(proc_bgr, use_gpu=self.config.ocr.gpu, min_conf=self.config.ocr.min_conf_keep)
            if tokens:
                source_used = "paddleocr"
            else:
                tokens = self.ocr_engine.run_easyocr(image_bgr)
                source_used = "easyocr"
        else:
            tokens = self.ocr_engine.run_easyocr(image_bgr)
            source_used = "easyocr"
        return tokens, source_used

    def _save_text_overlay(self, image: np.ndarray, tokens: List[OCRToken], image_stem: str, source: str) -> None:
        if not self.config.save_text_debug:
            return
        out_dir = Path(self.config.text_debug_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        overlay = draw_ocr_overlay(image, tokens)
        cv2.imwrite(str(out_dir / f"text_overlay_{image_stem}_{source}.png"), overlay)

    def _get_text_tokens_with_context(
        self,
        image_bgr: np.ndarray,
        context: Dict[str, Any],
        image_stem: str,
    ) -> tuple[list[OCRToken], Dict[str, Any], np.ndarray]:
        pdf_tokens: List[OCRToken] = []
        ocr_tokens: List[OCRToken] = []
        chosen = "unknown"
        analysis_image = image_bgr
        overlay_stem = str(context.get("plan_id") or image_stem)

        text_source = (self.config.text_source or "auto").lower()
        if text_source in {"auto", "pdf"}:
            bbox = context["crop_bbox_px_page"]
            crop_bbox = (float(bbox["x1"]), float(bbox["y1"]), float(bbox["x2"]), float(bbox["y2"]))
            pdf_tokens = extract_pdf_tokens_for_crop(
                pdf_path=str(context["pdf_path"]),
                page_number=int(context["page_number"]),
                crop_bbox_px_page=crop_bbox,
                render_dpi=int(context["crop_render_dpi"]),
                rotation_handling="auto",
            )
        pdf_count = len(pdf_tokens)
        use_pdf = text_source == "pdf" or (text_source == "auto" and pdf_count >= int(self.config.min_pdf_words))
        if text_source == "pdf" and pdf_count < int(self.config.min_pdf_words):
            LOGGER.warning("PDF text source requested but only %d words found (< min_pdf_words=%d).", pdf_count, int(self.config.min_pdf_words))
        if use_pdf:
            chosen = "pdf_text"
            tokens = pdf_tokens
            self._save_text_overlay(analysis_image, tokens, image_stem=overlay_stem, source=chosen)
            meta = {
                "text_source_used": chosen,
                "tokens_total": len(tokens),
                "pdf_words_total": len(tokens),
                "ocr_tokens_total": 0,
                "analysis_image_dpi_used": context.get("crop_render_dpi"),
            }
            return tokens, meta, analysis_image

        # OCR fallback: for PDF-originated crop, rerender at high DPI then run both YOLO+OCR on same image.
        bbox_pdf_points = self._context_bbox_pdf_points(context)
        if bbox_pdf_points is not None:
            analysis_image = render_pdf_crop(
                pdf_path=str(context["pdf_path"]),
                page_number=int(context["page_number"]),
                bbox_pdf_points=bbox_pdf_points,
                dpi=int(self.config.ocr.ocr_dpi),
            )
            context["analysis_image_dpi_used"] = int(self.config.ocr.ocr_dpi)
            analysis_inputs_dir = context.get("analysis_inputs_dir")
            if analysis_inputs_dir:
                p = Path(str(analysis_inputs_dir))
                p.mkdir(parents=True, exist_ok=True)
                plan_id = str(context.get("plan_id", "plan"))
                cv2.imwrite(str(p / f"{plan_id}_analysis_input.png"), analysis_image)
        ocr_tokens, source_used = self._run_ocr_fallback(analysis_image)
        chosen = source_used
        self._save_text_overlay(analysis_image, ocr_tokens, image_stem=overlay_stem, source=chosen)
        meta = {
            "text_source_used": chosen,
            "tokens_total": len(ocr_tokens),
            "pdf_words_total": pdf_count,
            "ocr_tokens_total": len(ocr_tokens),
            "analysis_image_dpi_used": context.get("analysis_image_dpi_used", context.get("crop_render_dpi")),
        }
        return ocr_tokens, meta, analysis_image

    def _run_per_room_ocr(self, image: np.ndarray, rooms: List[RoomInstance], image_name: str) -> None:
        """Legacy per-room OCR: crop each room, mask, OCR individually."""
        for room in rooms:
            crop, transform = extract_room_crop(image, room.polygon_simplified, self.config.room_crop_pad)
            local_poly = polygon_global_to_local(room.polygon_simplified, transform)
            masked = mask_outside_polygon(crop, local_poly)
            room_tokens_local = self.ocr_engine.run_easyocr(masked)
            room_tokens_global = self.ocr_engine.to_global(room_tokens_local, transform)
            room.ocr_tokens = room_tokens_global
            self._finalize_room_semantics(room)
            if self.config.save_debug:
                self._save_room_debug(
                    image_name=image_name, room=room,
                    raw_crop=crop, masked=masked,
                    local_tokens=room_tokens_local,
                )

    def _run_hybrid_ocr(self, image: np.ndarray, rooms: List[RoomInstance], image_name: str) -> None:
        """Two-pass approach:
        Pass 1: Per-room masked crop (good for both labels and dimensions on
                 upscaled crops, avoids cross-room text leakage)
        Pass 2: Full-image OCR to rescue rooms still missing dimensions
                 (catches boundary text that masking clips)
        """
        # Pass 1: Per-room crop OCR (primary -- good upscale, no cross-room noise)
        for room in rooms:
            crop, transform = extract_room_crop(
                image, room.polygon_simplified, self.config.room_crop_pad)
            local_poly = polygon_global_to_local(room.polygon_simplified, transform)
            masked = mask_outside_polygon(crop, local_poly)
            local_tokens = self.ocr_engine.run_easyocr(masked)
            room.ocr_tokens = self.ocr_engine.to_global(local_tokens, transform)
            if getattr(self.config.ocr, 'watermark_filter', False):
                room.ocr_tokens = filter_watermark_tokens(room.ocr_tokens)
            self._finalize_room_semantics(room)

        # Pass 2: Full-image OCR for rooms missing dimensions
        missing = [r for r in rooms if r.dimensions_text is None]
        if missing:
            all_tokens = self.ocr_engine.run_easyocr(image)
            if getattr(self.config.ocr, 'watermark_filter', False):
                all_tokens = filter_watermark_tokens(all_tokens)
            room_to_tokens = self._associate_tokens_to_rooms(all_tokens, rooms)
            for room in missing:
                extra = room_to_tokens.get(room.id, [])
                if not extra:
                    continue
                combined = room.ocr_tokens + extra
                combined = self.ocr_engine._dedupe(combined)
                room.ocr_tokens = combined
                self._finalize_room_semantics(room)
                if room.dimensions_text is not None:
                    room.meta["dimension_source"] = "full_image_fallback"

        # Pass 3: Raw crop (no mask) for rooms STILL missing dims
        still_missing = [r for r in rooms if r.dimensions_text is None]
        for room in still_missing:
            pad = max(self.config.room_crop_pad, 30)
            crop, transform = extract_room_crop(image, room.polygon_simplified, pad)
            crop_tokens = self.ocr_engine.run_easyocr(crop)
            crop_global = self.ocr_engine.to_global(crop_tokens, transform)
            if getattr(self.config.ocr, 'watermark_filter', False):
                crop_global = filter_watermark_tokens(crop_global)
            combined = room.ocr_tokens + crop_global
            combined = self.ocr_engine._dedupe(combined)
            room.ocr_tokens = combined
            self._finalize_room_semantics(room)
            if room.dimensions_text is not None:
                room.meta["dimension_source"] = "raw_crop_fallback"

        self._propagate_related_room_dimensions(rooms)

    def _finalize_room_semantics(self, room: RoomInstance) -> None:
        merged = merge_room_tokens(room.ocr_tokens)
        room.ocr_lines = merged.ocr_lines
        room.ocr_merged_text = merged.merged_text

        label, label_conf = pick_label(merged.ocr_lines, merged.line_tokens, self.config.parse)
        if label and label_conf >= self.config.parse.min_label_conf:
            room.label = label
            room.label_confidence = label_conf
        else:
            # Label falls back to YOLO class name; inherit YOLO detection
            # confidence since the segmentation model IS the label source.
            room.label = room.class_name
            room.label_confidence = room.yolo_conf

        dim = self._select_best_dimension_for_room(room, merged.ocr_lines, merged.merged_text, merged.line_tokens)
        if dim is not None:
            room.dimension_parsed = dim
            room.dimensions_text = dim.formatted
            room.area_ft2 = round(dim.w_total_ft * dim.h_total_ft, 4)
        else:
            room.dimension_parsed = None
            room.dimensions_text = None
            room.area_ft2 = None

        area_hits = [parse_area(line) for line in merged.ocr_lines]
        area_hits = [a for a in area_hits if a is not None]
        if area_hits:
            room.area_text = area_hits[0].raw
            if room.area_ft2 is None:
                room.area_ft2 = area_hits[0].sqft

    def _association_ratio(self, token: OCRToken, room: RoomInstance) -> float:
        box_area = token.box_poly.area
        if box_area <= 0:
            return 0.0
        inter = token.box_poly.intersection(room.polygon_simplified).area
        return float(inter / box_area)

    def _associate_tokens_to_rooms(self, tokens: List[OCRToken], rooms: List[RoomInstance]) -> Dict[int, List[OCRToken]]:
        mapping: Dict[int, List[OCRToken]] = {r.id: [] for r in rooms}
        for token in tokens:
            best_room: Optional[RoomInstance] = None
            best_ratio = 0.0
            for room in rooms:
                ratio = self._association_ratio(token, room)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_room = room
            if best_room is not None and best_ratio >= self.config.parse.intersection_ratio_threshold:
                mapping[best_room.id].append(token)
                continue
            cx = (token.box_bbox[0] + token.box_bbox[2]) / 2.0
            cy = (token.box_bbox[1] + token.box_bbox[3]) / 2.0
            p = Point(cx, cy)
            for room in rooms:
                if room.polygon_simplified.contains(p) or room.polygon_simplified.touches(p):
                    mapping[room.id].append(token)
                    break
        return mapping

    def _fill_missing_dimensions_from_full_image(self, image: np.ndarray, rooms: List[RoomInstance]) -> None:
        targets = [r for r in rooms if r.dimensions_text is None]
        if not targets:
            return
        all_tokens = self.ocr_engine.run_easyocr(image)
        room_to_tokens = self._associate_tokens_to_rooms(all_tokens, rooms)
        for room in targets:
            tokens = room_to_tokens.get(room.id, [])
            if not tokens:
                continue
            merged = merge_room_tokens(tokens)
            dim = self._select_best_dimension_for_room(room, merged.ocr_lines, merged.merged_text, merged.line_tokens)
            if dim is None:
                continue
            room.dimensions_text = dim.formatted
            room.dimension_parsed = dim
            room.area_ft2 = round(dim.w_total_ft * dim.h_total_ft, 4)
            room.meta["dimension_source"] = "full_image_fallback"

    def _select_best_dimension_for_room(self, room: RoomInstance, lines: List[str], merged_text: str, line_tokens) -> Optional:
        # Build candidates from line-level parser first.
        candidates = []
        base = best_dimension(lines, line_tokens, self.config.parse)
        if base is not None:
            candidates.append(base)
        for i, line in enumerate(lines):
            conf = 0.25
            if i < len(line_tokens) and line_tokens[i]:
                conf = float(sum(t.conf for t in line_tokens[i]) / len(line_tokens[i]))
            candidates.extend(parse_dimensions_candidates(line, conf=conf))
        if merged_text:
            candidates.extend(parse_dimensions_candidates(merged_text, conf=0.22))
            p = parse_dimensions(merged_text, conf=0.22)
            if p is not None:
                candidates.append(p)
        if not candidates:
            return None
        # Geometry-aware ranking to avoid noisy parses.
        minx, miny, maxx, maxy = room.polygon_simplified.bounds
        pw = max(maxx - minx, 1e-6)
        ph = max(maxy - miny, 1e-6)
        poly_ratio = max(pw, ph) / min(pw, ph)
        best = None
        best_score = -1e9
        for c in candidates:
            w = max(c.w_total_ft, c.h_total_ft)
            h = min(c.w_total_ft, c.h_total_ft)
            if h <= 0:
                continue
            # Reject obviously wrong dimensions
            if w < 2 or w > 45:
                continue
            if h < 2:
                continue
            dim_ratio = w / h
            ratio_penalty = abs(np.log(max(1e-6, dim_ratio / max(1e-6, poly_ratio))))
            area_ft2 = c.w_total_ft * c.h_total_ft
            # Tighter area bounds: typical rooms are 12-600 sqft
            if area_ft2 < 8 or area_ft2 > 800:
                area_penalty = 3.0
            elif area_ft2 < 16 or area_ft2 > 600:
                area_penalty = 1.5
            else:
                area_penalty = 0.0
            score = float(c.confidence) - 0.5 * ratio_penalty - area_penalty
            if score > best_score:
                best_score = score
                best = c
        return best

    def _propagate_related_room_dimensions(self, rooms: List[RoomInstance]) -> None:
        parsed_rooms = [r for r in rooms if r.dimension_parsed is not None]
        if not parsed_rooms:
            return
        for room in rooms:
            if room.dimension_parsed is not None:
                continue
            label = (room.label or room.class_name or "").lower()
            if not any(k in label for k in ["hall", "living", "dining"]):
                continue
            candidates = []
            for src in parsed_rooms:
                src_label = (src.label or src.class_name or "").lower()
                if not any(k in src_label for k in ["hall", "living", "dining"]):
                    continue
                dx = room.centroid[0] - src.centroid[0]
                dy = room.centroid[1] - src.centroid[1]
                dist2 = dx * dx + dy * dy
                candidates.append((dist2, src))
            if not candidates:
                continue
            candidates.sort(key=lambda x: x[0])
            src = candidates[0][1]
            room.dimension_parsed = src.dimension_parsed
            room.dimensions_text = src.dimensions_text
            room.area_ft2 = src.area_ft2
            room.meta["dimension_source"] = "related_room_propagation"

    def save_outputs(self, output: Dict, final_overlay: np.ndarray, output_dir: str, stem: str) -> Dict[str, str]:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / f"{stem}_data.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        vis_path = out_dir / f"{stem}_result.png"
        cv2.imwrite(str(vis_path), final_overlay)
        return {"json": str(json_path), "image": str(vis_path)}

    def _save_room_debug(
        self,
        image_name: str,
        room: RoomInstance,
        raw_crop: np.ndarray,
        masked: np.ndarray,
        local_tokens: List[OCRToken],
    ) -> None:
        room_dir = self.config.debug_path / image_name / f"room_{room.id:03d}"
        room_dir.mkdir(parents=True, exist_ok=True)
        save_debug_image(room_dir / "crop_raw.png", raw_crop)
        save_debug_image(room_dir / "crop_masked.png", masked)
        th, _ = preprocess_for_ocr(masked, self.config.ocr)
        save_debug_image(room_dir / "crop_preprocessed.png", th)
        overlay = draw_ocr_overlay(masked, local_tokens)
        save_debug_image(room_dir / "ocr_overlay.png", overlay)

    def save_final_visualization(self, image: np.ndarray, rooms: List[RoomInstance], out_path: str) -> None:
        vis = draw_final_overlay(image, rooms)
        cv2.imwrite(out_path, vis)

    def analyze_for_frontend(
        self,
        image: np.ndarray,
        image_path: str = "in_memory.png",
        plan_context: Optional[Dict[str, Any]] = None,
        include_debug: bool = False,
    ) -> Dict:
        """
        Analyze image and return frontend-ready JSON output.
        
        This method runs the full analysis pipeline and converts the results
        to the frontend-optimized JSON schema with structured confidence scores,
        parsed dimensions with inches, and optional debug payloads.
        
        Args:
            image: Input image as numpy array (BGR format)
            image_path: Path to the image file (for metadata)
            plan_context: Optional context dictionary for PDF-sourced images
            include_debug: Whether to include debug information in output
            
        Returns:
            Frontend-ready JSON dictionary
        """
        # Run the standard analysis
        output = self.analyze(image=image, image_path=image_path, plan_context=plan_context)
        
        # Extract metadata
        h, w = image.shape[:2]
        text_meta = output.get("text_metadata", {})
        text_strategy = text_meta.get("text_source_used", "unknown")
        
        # Determine source type from context
        source_type = "image"
        source_dpi = None
        plan_id = None
        page_index = 0
        
        if plan_context:
            if plan_context.get("pdf_path"):
                source_type = "pdf"
            source_dpi = plan_context.get("crop_render_dpi") or plan_context.get("analysis_image_dpi_used")
            plan_id = plan_context.get("plan_id")
            page_index = plan_context.get("page_number", 1) - 1  # Convert 1-indexed to 0-indexed
        
        # Build frontend output
        return build_frontend_output(
            image_path=image_path,
            image_width=w,
            image_height=h,
            rooms=self.last_rooms,
            text_strategy=text_strategy,
            include_debug=include_debug,
            source_type=source_type,
            source_dpi=source_dpi,
            plan_id=plan_id,
            page_index=page_index,
        )

    def analyze_path_for_frontend(
        self,
        image_path: str,
        plan_context: Optional[Dict[str, Any]] = None,
        include_debug: bool = False,
    ) -> Dict:
        """
        Load image from path and return frontend-ready JSON output.
        
        Args:
            image_path: Path to the image file
            plan_context: Optional context dictionary for PDF-sourced images
            include_debug: Whether to include debug information in output
            
        Returns:
            Frontend-ready JSON dictionary
        """
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Image not found or unreadable: {image_path}")
        return self.analyze_for_frontend(
            image=image,
            image_path=image_path,
            plan_context=plan_context,
            include_debug=include_debug,
        )
