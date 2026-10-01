from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import fitz
import numpy as np

from .features import score_image_thumbnail, score_text
from .regions import RegionCandidate, detect_candidate_regions, pad_bbox, score_crop
from .validators import ValidationResult, YoloFloorplanValidator


@dataclass
class ExtractConfig:
    pdf: str
    out_dir: str
    dpi: int = 450
    thumb_dpi: int = 120
    max_pages: Optional[int] = None
    min_page_score: float = 0.55
    min_crop_score: float = 0.60
    max_regions_per_page: int = 4
    min_region_area_ratio: float = 0.05
    pad_px: int = 20
    save_debug: bool = False
    debug_dir: Optional[str] = None
    validator: str = "yolo"
    yolo_model: Optional[str] = None
    min_rooms: int = 3
    device: str = "auto"
    scan_all_pages: bool = True
    rescue_top_pages: int = 8
    target_long_side: int = 4096


class PDFFloorPlanExtractor:
    def __init__(self, cfg: ExtractConfig):
        self.cfg = cfg
        self.pdf_path = Path(cfg.pdf)
        self.out_dir = Path(cfg.out_dir)
        self.floorplans_dir = self.out_dir / "floorplans"
        self.debug_dir = Path(cfg.debug_dir) if cfg.debug_dir else (self.out_dir / "debug")
        self.floorplans_dir.mkdir(parents=True, exist_ok=True)
        if cfg.save_debug:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.validator = self._build_validator()

    def _build_validator(self) -> Optional[YoloFloorplanValidator]:
        if self.cfg.validator == "none":
            return None
        model_path = self.cfg.yolo_model
        if not model_path:
            fallback = Path("results/runs/segment/runs/segment/floor_plan_rooms/weights/best.pt")
            if fallback.exists():
                model_path = str(fallback)
        if not model_path:
            return None
        try:
            return YoloFloorplanValidator(
                model_path=model_path,
                min_rooms=self.cfg.min_rooms,
                conf=0.25,
                imgsz=640,
                device=self.cfg.device,
            )
        except Exception:
            return None

    def _render_page(self, page: fitz.Page, dpi: int) -> np.ndarray:
        scale = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        # Keep extracted page render at ~4K long side for better OCR readability.
        target = int(max(0, self.cfg.target_long_side))
        if target > 0:
            h, w = bgr.shape[:2]
            long_side = max(h, w)
            if long_side < target:
                s = target / float(long_side)
                nw, nh = int(round(w * s)), int(round(h * s))
                bgr = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
        return bgr

    def _page_score(self, page: fitz.Page, page_idx: int) -> Dict:
        txt = page.get_text("text") or ""
        ts = score_text(txt)
        thumb = self._render_page(page, self.cfg.thumb_dpi)
        imf = score_image_thumbnail(thumb)
        if txt.strip():
            page_score = 0.65 * ts.score + 0.35 * imf.image_score
        else:
            page_score = imf.image_score
        page_score = float(np.clip(page_score, 0.0, 1.0))
        debug_thumb = None
        if self.cfg.save_debug and page_score >= self.cfg.min_page_score:
            tdir = self.debug_dir / "thumbs"
            tdir.mkdir(parents=True, exist_ok=True)
            debug_thumb = tdir / f"page_{page_idx + 1:03d}.png"
            cv2.imwrite(str(debug_thumb), thumb)
        return {
            "text_raw_len": len(txt),
            "room_hits": ts.room_hits,
            "context_hits": ts.context_hits,
            "neg_hits": ts.neg_hits,
            "text_score": ts.score,
            "edge_ratio": imf.edge_ratio,
            "line_count": imf.line_count,
            "orthogonal_ratio": imf.orthogonal_ratio,
            "colorfulness": imf.colorfulness,
            "image_score": imf.image_score,
            "page_score": page_score,
            "debug_thumb": None if debug_thumb is None else str(debug_thumb),
        }

    @staticmethod
    def _split_wide_candidates(
        cands: List[RegionCandidate],
        edge_mask: np.ndarray,
        page_w: int,
    ) -> List[RegionCandidate]:
        """Split very wide candidates into left/right when the middle is sparse."""
        out: List[RegionCandidate] = []
        for c in cands:
            bw = c.x2 - c.x1 + 1
            bh = c.y2 - c.y1 + 1
            width_ratio = bw / float(max(1, page_w))
            if width_ratio < 0.75:
                out.append(c)
                continue
            roi = edge_mask[c.y1 : c.y2 + 1, c.x1 : c.x2 + 1]
            if roi.size == 0:
                out.append(c)
                continue
            col_density = (roi > 0).mean(axis=0)
            mid_l = int(0.45 * bw)
            mid_r = int(0.55 * bw)
            if mid_r <= mid_l:
                out.append(c)
                continue
            mid_val = float(col_density[mid_l:mid_r].mean())
            all_val = float(col_density.mean())
            if mid_val >= 0.55 * max(all_val, 1e-6):
                out.append(c)
                continue
            cut = int((mid_l + mid_r) / 2)
            l = RegionCandidate(
                x1=c.x1,
                y1=c.y1,
                x2=c.x1 + cut - 1,
                y2=c.y2,
                area_ratio=0.0,
                edge_density=c.edge_density,
            )
            r = RegionCandidate(
                x1=c.x1 + cut,
                y1=c.y1,
                x2=c.x2,
                y2=c.y2,
                area_ratio=0.0,
                edge_density=c.edge_density,
            )
            out.extend([l, r])
        return out

    def run(self) -> Dict:
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        doc = fitz.open(str(self.pdf_path))
        page_count = doc.page_count
        limit = page_count if self.cfg.max_pages is None else min(page_count, int(self.cfg.max_pages))
        items: List[Dict] = []
        page_logs: List[Dict] = []
        pages_with_floorplans: List[int] = []
        page_scores: List[Dict] = []

        for pi in range(limit):
            page = doc[pi]
            pscore = self._page_score(page, pi)
            page_scores.append({"page_number": pi + 1, **pscore})

        # Always inspect all pages by default to avoid missing true floor-plan pages.
        pages_to_process = {p["page_number"] for p in page_scores} if self.cfg.scan_all_pages else set()
        if not pages_to_process:
            for p in page_scores:
                if p["page_score"] >= self.cfg.min_page_score:
                    pages_to_process.add(p["page_number"])
            # Rescue pass: also inspect top image-score pages even if text score is weak.
            top_rescue = sorted(page_scores, key=lambda x: x["image_score"], reverse=True)[: self.cfg.rescue_top_pages]
            for p in top_rescue:
                pages_to_process.add(p["page_number"])

        for pi in range(limit):
            page = doc[pi]
            pscore = page_scores[pi]
            log = {"page_number": pi + 1, **{k: pscore[k] for k in pscore if k != "page_number"}, "status": "not_processed"}
            if (pi + 1) not in pages_to_process:
                log["status"] = "skipped_by_page_selection"
                page_logs.append(log)
                continue

            page_img = self._render_page(page, self.cfg.dpi)
            page_val = ValidationResult(True, 0, 0.0, "page_validator_none")
            if self.validator is not None:
                page_val = self.validator.validate(page_img)
            log["page_yolo_room_count"] = page_val.room_count
            log["page_yolo_conf_avg"] = page_val.conf_avg

            if self.validator is not None:
                weak_page = page_val.room_count <= 0 and pscore["page_score"] < max(0.45, self.cfg.min_page_score - 0.05)
                if weak_page:
                    log["status"] = "skip_page_low_signal"
                    page_logs.append(log)
                    continue

            cands, edge_mask = detect_candidate_regions(
                page_img_bgr=page_img,
                min_region_area_ratio=self.cfg.min_region_area_ratio,
                max_regions_per_page=self.cfg.max_regions_per_page,
            )
            cands = self._split_wide_candidates(cands, edge_mask=edge_mask, page_w=page_img.shape[1])
            cands = sorted(cands, key=lambda c: ((c.x2 - c.x1 + 1) * (c.y2 - c.y1 + 1)), reverse=True)[
                : self.cfg.max_regions_per_page
            ]
            if self.cfg.save_debug:
                pdir = self.debug_dir / f"page_{pi + 1:03d}"
                pdir.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(pdir / "render.png"), page_img)
                cv2.imwrite(str(pdir / "edges.png"), edge_mask)
                viz = page_img.copy()
                for idx, c in enumerate(cands, start=1):
                    cv2.rectangle(viz, (c.x1, c.y1), (c.x2, c.y2), (0, 255, 255), 2)
                    cv2.putText(viz, f"R{idx}", (c.x1, max(20, c.y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.imwrite(str(pdir / "candidates.png"), viz)

            log["candidate_count"] = len(cands)
            used_page_fallback_candidate = False
            if not cands:
                if self.validator is not None and page_val.room_count >= max(2, self.cfg.min_rooms - 1):
                    h, w = page_img.shape[:2]
                    mx = int(0.03 * w)
                    my = int(0.05 * h)
                    cands = [
                        RegionCandidate(
                            x1=mx,
                            y1=my,
                            x2=w - 1 - mx,
                            y2=h - 1 - my,
                            area_ratio=((w - 2 * mx) * (h - 2 * my)) / float(max(1, w * h)),
                            edge_density=0.0,
                        )
                    ]
                    log["candidate_count"] = 1
                    log["status"] = "fallback_page_crop"
                    used_page_fallback_candidate = True
                else:
                    log["status"] = "no_candidates"
                    page_logs.append(log)
                    continue

            accepted_on_page = 0
            next_region_index = 1
            min_crop_for_page = self.cfg.min_crop_score
            if pscore["page_score"] < self.cfg.min_page_score:
                min_crop_for_page = max(0.48, self.cfg.min_crop_score - 0.10)
            for ri, c in enumerate(cands, start=1):
                h, w = page_img.shape[:2]
                x1, y1, x2, y2 = pad_bbox(c.x1, c.y1, c.x2, c.y2, self.cfg.pad_px, w, h)
                crop = page_img[y1 : y2 + 1, x1 : x2 + 1].copy()
                base_crop_score = score_crop(crop)
                # Text-aware bonus: only helps on pages with strong room/context evidence.
                text_bonus = min(0.25, pscore["room_hits"] * 0.004 + pscore["context_hits"] * 0.01)
                c.crop_score = float(np.clip(base_crop_score + text_bonus, 0.0, 1.0))

                val_result = ValidationResult(True, 0, 0.0, "validator_none")
                accept_candidate = False
                page_plan_like = (
                    (pscore["room_hits"] >= 2 and pscore["context_hits"] >= 2)
                    or pscore["page_score"] >= 0.62
                    or (
                        pscore["orthogonal_ratio"] >= 0.90
                        and pscore["edge_ratio"] >= 0.04
                        and pscore["colorfulness"] < 35.0
                    )
                )
                if self.validator is not None:
                    val_result = self.validator.validate(crop)
                    if val_result.accepted:
                        # Strong validator pass should override handcrafted crop score gates.
                        if val_result.room_count >= self.cfg.min_rooms and val_result.conf_avg >= 0.50:
                            accept_candidate = True
                            val_result = ValidationResult(
                                accepted=True,
                                room_count=val_result.room_count,
                                conf_avg=val_result.conf_avg,
                                reason="validator_strong_override",
                            )
                        else:
                            # Otherwise still require plan-like page/crop signal.
                            accept_candidate = (
                                val_result.conf_avg >= 0.35
                                and (
                                    page_plan_like
                                    or c.crop_score >= max(0.52, min_crop_for_page - 0.05)
                                )
                            )
                        if used_page_fallback_candidate:
                            accept_candidate = val_result.conf_avg >= 0.50
                    else:
                        # Soft-accept when YOLO finds at least some room evidence on plan-like pages.
                        soft_ok = (
                            page_plan_like
                            and val_result.room_count >= max(1, self.cfg.min_rooms - 2)
                            and c.crop_score >= max(0.58, min_crop_for_page - 0.04)
                            and c.area_ratio >= max(self.cfg.min_region_area_ratio, 0.04)
                            and val_result.conf_avg >= 0.30
                        )
                        # Geometry-led rescue for pages where text extraction is weak/unreliable.
                        geom_rescue_ok = (
                            val_result.room_count >= 2
                            and val_result.conf_avg >= 0.30
                            and c.crop_score >= 0.68
                            and pscore["page_score"] >= 0.25
                            and c.area_ratio >= max(self.cfg.min_region_area_ratio, 0.06)
                        )
                        if soft_ok or geom_rescue_ok:
                            accept_candidate = True
                            val_result = ValidationResult(
                                accepted=True,
                                room_count=val_result.room_count,
                                conf_avg=val_result.conf_avg,
                                reason="soft_accept" if soft_ok else "geom_rescue",
                            )
                else:
                    accept_candidate = c.crop_score >= min_crop_for_page

                if not accept_candidate:
                    continue

                ri = next_region_index
                next_region_index += 1
                out_name = f"{self.pdf_path.stem}_p{pi + 1:02d}_r{ri:02d}.png"
                out_abs = self.floorplans_dir / out_name
                cv2.imwrite(str(out_abs), crop)
                item = {
                    "source_pdf": str(self.pdf_path),
                    "page_number": pi + 1,
                    "region_index": ri,
                    "bbox_px": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
                    "page_score": pscore["page_score"],
                    "text_score": pscore["text_score"],
                    "image_score": pscore["image_score"],
                    "crop_score": c.crop_score,
                    "crop_score_base": base_crop_score,
                    "crop_text_bonus": text_bonus,
                    "validator": "yolo" if self.validator is not None else "none",
                    "yolo_room_count": val_result.room_count,
                    "yolo_conf_avg": val_result.conf_avg,
                    "validator_reason": val_result.reason,
                    "output_image": str(Path("floorplans") / out_name),
                    "width": int(crop.shape[1]),
                    "height": int(crop.shape[0]),
                }
                items.append(item)
                accepted_on_page += 1

            if accepted_on_page > 0:
                pages_with_floorplans.append(pi + 1)
                log["status"] = "accepted"
                log["accepted_regions"] = accepted_on_page
            else:
                log["status"] = "validator_or_crop_reject"
            page_logs.append(log)

        summary = {
            "pdf": str(self.pdf_path),
            "page_count": int(page_count),
            "processed_pages": int(limit),
            "extracted_count": len(items),
            "pages_with_floorplans": pages_with_floorplans,
            "items": items,
            "page_logs": page_logs,
        }
        manifest_path = self.out_dir / "manifest.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        if self.cfg.save_debug:
            csv_path = self.debug_dir / "page_scores.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "page_number",
                        "room_hits",
                        "context_hits",
                        "neg_hits",
                        "text_score",
                        "edge_ratio",
                        "line_count",
                        "orthogonal_ratio",
                        "colorfulness",
                        "image_score",
                        "page_score",
                        "status",
                        "accepted_regions",
                    ]
                )
                for log in page_logs:
                    writer.writerow(
                        [
                            log["page_number"],
                            log["room_hits"],
                            log["context_hits"],
                            log["neg_hits"],
                            f"{log['text_score']:.6f}",
                            f"{log['edge_ratio']:.6f}",
                            log["line_count"],
                            f"{log['orthogonal_ratio']:.6f}",
                            f"{log['colorfulness']:.6f}",
                            f"{log['image_score']:.6f}",
                            f"{log['page_score']:.6f}",
                            log["status"],
                            log.get("accepted_regions", 0),
                        ]
                    )

        if len(items) == 0:
            raise RuntimeError(
                "No floor plan crops were extracted. Try lowering --min_page_score, --min_crop_score, or --min_rooms."
            )
        return summary


def extract_floorplans_from_pdf(
    pdf_path: str,
    out_dir: str,
    config: ExtractConfig,
) -> List[Dict]:
    """
    Importable extractor API.
    Keeps CLI behavior intact while exposing core functionality for orchestration.
    Returns extracted item records from generated manifest.
    """
    cfg = config
    cfg.pdf = pdf_path
    cfg.out_dir = out_dir
    summary = PDFFloorPlanExtractor(cfg).run()
    return summary.get("items", [])
