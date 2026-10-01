"""
Frontend-Ready JSON Output Schema
=================================
Converts pipeline output to a structured JSON format optimized for frontend consumption.

This module provides:
- Dataclasses for the frontend JSON structure
- Builder function to convert RoomInstance list to frontend format
- Support for multi-page PDF outputs
- Optional debug payload inclusion
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

# Import types only for type checking to avoid circular/heavy imports
if TYPE_CHECKING:
    from .types import DimensionParseResult, OCRToken, RoomInstance


SCHEMA_VERSION = "1.0.0"


def has_room_label(label: Optional[str]) -> bool:
    """True if a room has a real label, i.e. anything except the generic
    "room" class. The YOLO model is multi-class, so a label that matches the
    detected class name (e.g. OCR and YOLO both say "Hall") still counts."""
    return bool(label) and label.strip().lower() != "room"


# =============================================================================
# FRONTEND DATACLASSES
# =============================================================================


@dataclass
class FrontendDimensionsParsed:
    """Parsed dimension values with total inches for easy computation."""
    width_ft: int
    width_in: float
    height_ft: int
    height_in: float
    width_total_inches: float
    height_total_inches: float
    area_sqft: float

    @classmethod
    def from_dimension_result(cls, dim: DimensionParseResult) -> "FrontendDimensionsParsed":
        """Convert from internal DimensionParseResult."""
        w_total_inches = (dim.w_ft * 12) + dim.w_in
        h_total_inches = (dim.h_ft * 12) + dim.h_in
        area_sqft = round(dim.w_total_ft * dim.h_total_ft, 2)
        return cls(
            width_ft=dim.w_ft,
            width_in=float(dim.w_in),
            height_ft=dim.h_ft,
            height_in=float(dim.h_in),
            width_total_inches=round(w_total_inches, 2),
            height_total_inches=round(h_total_inches, 2),
            area_sqft=area_sqft,
        )


@dataclass
class FrontendArea:
    """Area information with source tracking."""
    value_sqft: Optional[float]
    source: str  # "computed_from_dimensions", "ocr_text", "none"
    raw_text: Optional[str] = None


@dataclass
class FrontendConfidence:
    """Structured confidence scores for frontend display."""
    geometry: float  # YOLO detection confidence
    label: float     # Label extraction confidence
    dimensions: float  # Dimension parsing confidence


@dataclass
class FrontendGeometry:
    """Geometric properties of a room."""
    centroid: Dict[str, float]  # {"x": ..., "y": ...}
    bbox: Dict[str, int]  # {"x1": ..., "y1": ..., "x2": ..., "y2": ...}
    polygon: List[List[float]]  # [[x, y], ...]
    area_pixels: float


@dataclass
class FrontendDebug:
    """Debug information for development/QA review."""
    text_blob: Optional[str] = None
    ocr_tokens: Optional[List[Dict[str, Any]]] = None
    ocr_lines: Optional[List[str]] = None
    dimension_source: Optional[str] = None


@dataclass
class FrontendRoom:
    """Complete room representation for frontend."""
    id: int
    label: Optional[str]
    label_raw: Optional[str]
    dimensions: Optional[str]
    dimensions_raw: Optional[str]
    dimensions_parsed: Optional[FrontendDimensionsParsed]
    area: FrontendArea
    confidence: FrontendConfidence
    geometry: FrontendGeometry
    debug: Optional[FrontendDebug] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling nested dataclasses."""
        d = {
            "id": self.id,
            "label": self.label,
            "label_raw": self.label_raw,
            "dimensions": self.dimensions,
            "dimensions_raw": self.dimensions_raw,
            "dimensions_parsed": asdict(self.dimensions_parsed) if self.dimensions_parsed else None,
            "area": asdict(self.area),
            "confidence": asdict(self.confidence),
            "geometry": asdict(self.geometry),
        }
        if self.debug is not None:
            d["debug"] = asdict(self.debug)
        return d


@dataclass
class FrontendPageSummary:
    """Per-page statistics for quality assessment."""
    total_rooms: int
    rooms_with_labels: int
    rooms_with_dimensions: int
    rooms_with_area: int
    text_strategy: str  # "pdf_text", "ocr_per_room", "easyocr", "paddleocr"
    warnings: List[str] = field(default_factory=list)


@dataclass
class FrontendPage:
    """Single page/plan in the output."""
    page_index: int
    plan_id: Optional[str]
    image_path: str
    image_dimensions: Dict[str, int]  # {"width": ..., "height": ...}
    summary: FrontendPageSummary
    rooms: List[FrontendRoom]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page_index": self.page_index,
            "plan_id": self.plan_id,
            "image_path": self.image_path,
            "image_dimensions": self.image_dimensions,
            "summary": asdict(self.summary),
            "rooms": [r.to_dict() for r in self.rooms],
        }


@dataclass
class FrontendSource:
    """Source metadata."""
    type: str  # "pdf" or "image"
    file: str
    dpi: Optional[int] = None
    total_pages: int = 1


@dataclass
class FrontendOutput:
    """Top-level frontend output structure."""
    schema_version: str
    generated_at: str
    source: FrontendSource
    pages: List[FrontendPage]

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire output to dictionary."""
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "source": asdict(self.source),
            "pages": [p.to_dict() for p in self.pages],
        }


# =============================================================================
# CONVERSION FUNCTIONS
# =============================================================================


def _room_to_frontend(
    room: "RoomInstance",
    include_debug: bool = False,
) -> FrontendRoom:
    """Convert a RoomInstance to FrontendRoom format."""
    # Lazy import to avoid circular dependencies
    from .types import DimensionParseResult
    
    # Parse dimensions
    dim_parsed = None
    if room.dimension_parsed is not None:
        dim_parsed = FrontendDimensionsParsed.from_dimension_result(room.dimension_parsed)

    # Determine area source
    area_source = "none"
    area_value = None
    if room.area_ft2 is not None:
        area_value = round(room.area_ft2, 2)
        if room.area_text:
            area_source = "ocr_text"
        elif room.dimension_parsed:
            area_source = "computed_from_dimensions"

    area = FrontendArea(
        value_sqft=area_value,
        source=area_source,
        raw_text=room.area_text,
    )

    # Confidence scores
    dim_conf = 0.0
    if room.dimension_parsed is not None:
        dim_conf = room.dimension_parsed.confidence
    confidence = FrontendConfidence(
        geometry=round(float(room.yolo_conf), 4),
        label=round(float(room.label_confidence), 4),
        dimensions=round(float(dim_conf), 4),
    )

    # Geometry
    poly_coords = [[round(float(x), 2), round(float(y), 2)] for x, y in room.polygon_simplified.exterior.coords]
    minx, miny, maxx, maxy = room.polygon_simplified.bounds
    geometry = FrontendGeometry(
        centroid={"x": round(float(room.centroid[0]), 2), "y": round(float(room.centroid[1]), 2)},
        bbox={"x1": int(minx), "y1": int(miny), "x2": int(maxx), "y2": int(maxy)},
        polygon=poly_coords,
        area_pixels=round(float(room.area_px2), 2),
    )

    # Debug info (optional)
    debug = None
    if include_debug:
        ocr_tokens_list = None
        if room.ocr_tokens:
            ocr_tokens_list = [
                {
                    "text": t.text,
                    "conf": round(float(t.conf), 4),
                    "bbox": [round(float(v), 2) for v in t.box_bbox],
                    "source": t.source,
                }
                for t in room.ocr_tokens
            ]
        debug = FrontendDebug(
            text_blob=room.ocr_merged_text if room.ocr_merged_text else None,
            ocr_tokens=ocr_tokens_list,
            ocr_lines=room.ocr_lines if room.ocr_lines else None,
            dimension_source=room.meta.get("dimension_source"),
        )

    return FrontendRoom(
        id=room.id,
        label=room.label,
        label_raw=room.label,
        dimensions=room.dimensions_text,
        dimensions_raw=room.dimension_parsed.raw if room.dimension_parsed else None,
        dimensions_parsed=dim_parsed,
        area=area,
        confidence=confidence,
        geometry=geometry,
        debug=debug,
    )


def build_frontend_output(
    image_path: str,
    image_width: int,
    image_height: int,
    rooms: List[RoomInstance],
    text_strategy: str = "unknown",
    include_debug: bool = False,
    source_type: str = "image",
    source_dpi: Optional[int] = None,
    plan_id: Optional[str] = None,
    page_index: int = 0,
) -> Dict[str, Any]:
    """
    Build frontend-ready JSON output from pipeline results.

    Args:
        image_path: Path to the analyzed image
        image_width: Image width in pixels
        image_height: Image height in pixels
        rooms: List of RoomInstance objects from analysis
        text_strategy: Text extraction strategy used
        include_debug: Whether to include debug payloads
        source_type: "pdf" or "image"
        source_dpi: DPI if from PDF
        plan_id: Plan identifier (for PDF pages)
        page_index: Page index in multi-page document

    Returns:
        Frontend-ready JSON dictionary
    """
    # Convert rooms
    frontend_rooms = [_room_to_frontend(r, include_debug=include_debug) for r in rooms]

    # Calculate summary statistics
    rooms_with_labels = sum(1 for r in rooms if has_room_label(r.label))
    rooms_with_dimensions = sum(1 for r in rooms if r.dimensions_text)
    rooms_with_area = sum(1 for r in rooms if r.area_ft2 is not None)

    # Generate warnings
    warnings = []
    if len(rooms) == 0:
        warnings.append("No rooms detected in image")
    elif rooms_with_labels == 0:
        warnings.append("No room labels extracted - OCR may have failed")
    if rooms_with_dimensions == 0 and len(rooms) > 0:
        warnings.append("No dimensions extracted - text may be too small or unclear")
    if text_strategy in ("easyocr", "paddleocr") and source_type == "pdf":
        warnings.append("PDF has no text layer - OCR fallback used")

    summary = FrontendPageSummary(
        total_rooms=len(rooms),
        rooms_with_labels=rooms_with_labels,
        rooms_with_dimensions=rooms_with_dimensions,
        rooms_with_area=rooms_with_area,
        text_strategy=text_strategy,
        warnings=warnings,
    )

    page = FrontendPage(
        page_index=page_index,
        plan_id=plan_id,
        image_path=str(image_path),
        image_dimensions={"width": image_width, "height": image_height},
        summary=summary,
        rooms=frontend_rooms,
    )

    source = FrontendSource(
        type=source_type,
        file=Path(image_path).name,
        dpi=source_dpi,
        total_pages=1,
    )

    output = FrontendOutput(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source=source,
        pages=[page],
    )

    return output.to_dict()


def build_frontend_output_multipage(
    source_file: str,
    source_type: str,
    source_dpi: Optional[int],
    pages_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build frontend-ready JSON output for multi-page documents.

    Args:
        source_file: Original source file path
        source_type: "pdf" or "image"
        source_dpi: DPI if from PDF
        pages_data: List of page data dictionaries, each containing:
            - image_path: str
            - image_width: int
            - image_height: int
            - rooms: List[RoomInstance]
            - text_strategy: str
            - plan_id: Optional[str]
            - page_index: int
            - include_debug: bool

    Returns:
        Frontend-ready JSON dictionary with all pages
    """
    pages = []
    for pd in pages_data:
        frontend_rooms = [_room_to_frontend(r, include_debug=pd.get("include_debug", False)) for r in pd["rooms"]]

        rooms_with_labels = sum(1 for r in pd["rooms"] if has_room_label(r.label))
        rooms_with_dimensions = sum(1 for r in pd["rooms"] if r.dimensions_text)
        rooms_with_area = sum(1 for r in pd["rooms"] if r.area_ft2 is not None)

        warnings = []
        if len(pd["rooms"]) == 0:
            warnings.append("No rooms detected in image")
        elif rooms_with_labels == 0:
            warnings.append("No room labels extracted")
        if rooms_with_dimensions == 0 and len(pd["rooms"]) > 0:
            warnings.append("No dimensions extracted")
        text_strategy = pd.get("text_strategy", "unknown")
        if text_strategy in ("easyocr", "paddleocr") and source_type == "pdf":
            warnings.append("PDF has no text layer - OCR fallback used")

        summary = FrontendPageSummary(
            total_rooms=len(pd["rooms"]),
            rooms_with_labels=rooms_with_labels,
            rooms_with_dimensions=rooms_with_dimensions,
            rooms_with_area=rooms_with_area,
            text_strategy=text_strategy,
            warnings=warnings,
        )

        page = FrontendPage(
            page_index=pd.get("page_index", 0),
            plan_id=pd.get("plan_id"),
            image_path=str(pd["image_path"]),
            image_dimensions={"width": pd["image_width"], "height": pd["image_height"]},
            summary=summary,
            rooms=frontend_rooms,
        )
        pages.append(page)

    source = FrontendSource(
        type=source_type,
        file=Path(source_file).name,
        dpi=source_dpi,
        total_pages=len(pages),
    )

    output = FrontendOutput(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source=source,
        pages=pages,
    )

    return output.to_dict()


def convert_legacy_output_to_frontend(
    legacy_output: Dict[str, Any],
    include_debug: bool = False,
) -> Dict[str, Any]:
    """
    Convert existing pipeline output format to frontend format.

    This is useful for converting previously generated JSON files
    without re-running the full analysis.
    
    Supports multiple legacy formats:
    - v2 format: has "image" dict with filename/path/width/height
    - v1 format: has "source_image" string and "summary" dict

    Args:
        legacy_output: Output dictionary from existing pipeline
        include_debug: Whether to include debug information

    Returns:
        Frontend-ready JSON dictionary
    """
    # Detect format version and extract common fields
    image_info = legacy_output.get("image", {})
    text_meta = legacy_output.get("text_metadata", {})
    
    # Handle v1 format (source_image string)
    if "source_image" in legacy_output and not image_info:
        source_path = Path(legacy_output["source_image"])
        image_info = {
            "filename": source_path.name,
            "path": str(source_path),
            "width": 0,
            "height": 0,
        }
    
    # Build rooms from legacy format
    rooms_data = []
    for idx, r in enumerate(legacy_output.get("rooms", [])):
        dim_parsed = None
        if r.get("dimension_parsed"):
            dp = r["dimension_parsed"]
            w_total_inches = (dp.get("w_ft", 0) * 12) + dp.get("w_in", 0)
            h_total_inches = (dp.get("h_ft", 0) * 12) + dp.get("h_in", 0)
            dim_parsed = {
                "width_ft": dp.get("w_ft", 0),
                "width_in": float(dp.get("w_in", 0)),
                "height_ft": dp.get("h_ft", 0),
                "height_in": float(dp.get("h_in", 0)),
                "width_total_inches": round(w_total_inches, 2),
                "height_total_inches": round(h_total_inches, 2),
                "area_sqft": round(dp.get("w_total_ft", 0) * dp.get("h_total_ft", 0), 2),
            }

        # Determine area source
        area_source = "none"
        area_value = r.get("area_ft2")
        if area_value is not None:
            if r.get("area_text"):
                area_source = "ocr_text"
            elif r.get("dimension_parsed"):
                area_source = "computed_from_dimensions"

        # Build polygon/bbox from different formats
        poly = r.get("polygon_coordinates", [])
        bbox_arr = r.get("bbox", [])
        
        if poly:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            bbox = {"x1": int(min(xs)), "y1": int(min(ys)), "x2": int(max(xs)), "y2": int(max(ys))}
        elif bbox_arr and len(bbox_arr) == 4:
            # v1 format: bbox is [x1, y1, x2, y2]
            bbox = {"x1": int(bbox_arr[0]), "y1": int(bbox_arr[1]), "x2": int(bbox_arr[2]), "y2": int(bbox_arr[3])}
            # Convert bbox to simple polygon (rectangle)
            poly = [
                [bbox_arr[0], bbox_arr[1]],
                [bbox_arr[2], bbox_arr[1]],
                [bbox_arr[2], bbox_arr[3]],
                [bbox_arr[0], bbox_arr[3]],
            ]
        else:
            bbox = {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
        
        # Get confidence - handle both formats
        geom_conf = r.get("yolo_confidence") or r.get("confidence") or 0
        label_conf = r.get("label_confidence", 0)
        # When label_confidence is 0 but a label exists, the label came from
        # the YOLO segmentation model, so inherit its detection confidence.
        if label_conf == 0 and (r.get("label") or r.get("name")):
            label_conf = geom_conf
        dim_conf = 0.0
        if r.get("dimension_parsed"):
            dim_conf = r["dimension_parsed"].get("confidence", 0)

        room_dict = {
            "id": r.get("id", idx + 1),
            "label": r.get("label") or r.get("name"),
            "label_raw": r.get("label") or r.get("name"),
            "dimensions": r.get("dimensions_text") or r.get("dimensions"),
            "dimensions_raw": r.get("dimension_parsed", {}).get("raw") if r.get("dimension_parsed") else None,
            "dimensions_parsed": dim_parsed,
            "area": {
                "value_sqft": round(area_value, 2) if area_value else None,
                "source": area_source,
                "raw_text": r.get("area_text"),
            },
            "confidence": {
                "geometry": round(float(geom_conf), 4),
                "label": round(float(label_conf), 4),
                "dimensions": round(float(dim_conf), 4),
            },
            "geometry": {
                "centroid": r.get("centroid", {"x": 0, "y": 0}),
                "bbox": bbox,
                "polygon": poly,
                "area_pixels": r.get("area_px2") or r.get("area_pixels", 0),
            },
        }

        if include_debug:
            room_dict["debug"] = {
                "text_blob": r.get("ocr_merged_text"),
                "ocr_tokens": r.get("ocr_raw"),
                "ocr_lines": r.get("ocr_lines"),
                "dimension_source": r.get("dimension_source"),
            }

        rooms_data.append(room_dict)

    # Calculate summary
    rooms_with_labels = sum(1 for r in rooms_data if has_room_label(r["label"]))
    rooms_with_dimensions = sum(1 for r in rooms_data if r["dimensions"])
    rooms_with_area = sum(1 for r in rooms_data if r["area"]["value_sqft"])

    warnings = []
    if len(rooms_data) == 0:
        warnings.append("No rooms detected")
    elif rooms_with_labels == 0:
        warnings.append("No room labels extracted")
    if rooms_with_dimensions == 0 and len(rooms_data) > 0:
        warnings.append("No dimensions extracted")

    text_strategy = text_meta.get("text_source_used", "unknown")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "type": "image",
            "file": image_info.get("filename", "unknown"),
            "dpi": text_meta.get("analysis_image_dpi_used"),
            "total_pages": 1,
        },
        "pages": [
            {
                "page_index": 0,
                "plan_id": None,
                "image_path": image_info.get("path", ""),
                "image_dimensions": {
                    "width": image_info.get("width", 0),
                    "height": image_info.get("height", 0),
                },
                "summary": {
                    "total_rooms": len(rooms_data),
                    "rooms_with_labels": rooms_with_labels,
                    "rooms_with_dimensions": rooms_with_dimensions,
                    "rooms_with_area": rooms_with_area,
                    "text_strategy": text_strategy,
                    "warnings": warnings,
                },
                "rooms": rooms_data,
            }
        ],
    }
