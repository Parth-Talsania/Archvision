"""
Floor Plan Analysis Pipeline
============================
Integrated pipeline combining:
    1. YOLOv8-Seg for room instance segmentation
    2. EasyOCR for text extraction (room names, dimensions)
    3. Shapely Point-in-Polygon for mapping text to rooms

Prerequisites:
    pip install ultralytics easyocr shapely opencv-python numpy pymupdf

Usage:
    from floor_plan_pipeline import FloorPlanAnalyzer
    
    analyzer = FloorPlanAnalyzer(model_path="best.pt")
    results = analyzer.analyze("floor_plan.png")
    
    # Results contain rooms with their names and dimensions
    for room in results:
        print(f"{room['name']}: {room['dimensions']}")
"""

import cv2
import re
import os
import base64
import time
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union, Set
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import easyocr
import requests
from ultralytics import YOLO
from shapely.geometry import Polygon, Point
from shapely.validation import make_valid
from shapely import affinity

# Optional: Roboflow inference SDK
try:
    from inference_sdk import InferenceHTTPClient
    ROBOFLOW_SDK_AVAILABLE = True
except ImportError:
    ROBOFLOW_SDK_AVAILABLE = False

# Roboflow API key (set via ROBOFLOW_API_KEY environment variable)
ROBOFLOW_API_KEY = os.environ.get("ROBOFLOW_API_KEY", "")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TextRegion:
    """Detected text from OCR."""
    text: str
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    center: Tuple[float, float]
    confidence: float
    text_type: str = "unknown"  # "label", "dimension", "area"


@dataclass
class DetectedRoom:
    """Room detected by YOLO with associated text."""
    polygon: Polygon
    class_name: str  # From YOLO (e.g., "Bedroom")
    confidence: float
    bbox: Tuple[int, int, int, int]
    area_pixels: float
    mask_points: np.ndarray
    # Mapped from OCR:
    label: Optional[str] = None  # e.g., "Master Bed"
    dimensions: Optional[str] = None  # e.g., "12x10", "12'x10'"
    area_text: Optional[str] = None  # e.g., "120 sq.ft"
    dimension_source: Optional[str] = None  # direct, fragment_fallback, nearest_room
    dimension_confidence: float = 0.0


@dataclass
class PDFRenderContext:
    dpi: int
    zoom: float
    matrix: "fitz.Matrix"
    rotation: int
    width_px: int
    height_px: int


# =============================================================================
# MAIN PIPELINE CLASS
# =============================================================================

class FloorPlanAnalyzer:
    """
    Complete floor plan analysis pipeline.
    
    Workflow:
        1. detect_rooms() - YOLO instance segmentation
        2. extract_text() - EasyOCR text detection
        3. map_text_to_rooms() - Point-in-Polygon matching
        4. analyze() - Full pipeline in one call
    """
    
    def __init__(
        self,
        model_path: Union[str, Path],
        ocr_languages: List[str] = ['en'],
        use_gpu: bool = True
    ):
        """
        Initialize the analyzer.
        
        Args:
            model_path: Path to trained YOLOv8-Seg model (best.pt)
            ocr_languages: Languages for EasyOCR (default: ['en'])
            use_gpu: Whether to use GPU for OCR (default: True)
        """
        # Load YOLO model
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        print(f"[INFO] Loading YOLO model: {self.model_path.name}")
        self.yolo_model = YOLO(str(self.model_path))
        
        # Initialize EasyOCR
        print(f"[INFO] Initializing EasyOCR with languages: {ocr_languages}")
        self.ocr_reader = easyocr.Reader(ocr_languages, gpu=use_gpu)
        
        # Regex patterns for text classification
        # ---------------------------------------------------------------------
        # DIMENSION PATTERNS (ordered from most specific to least specific)
        # These handle various OCR fragmentation scenarios
        # ---------------------------------------------------------------------
        self.dimension_patterns = [
            # Pattern 1: Full architectural format "12'-6" x 10'-0"" with various quote styles
            re.compile(
                r"(\d+)\s*['\'\`\Â´]+\s*[-â€“â€”]?\s*(\d+)\s*[\"\"\'\']+\s*[xXÃ—\*]\s*(\d+)\s*['\'\`\Â´]+\s*[-â€“â€”]?\s*(\d+)\s*[\"\"\'\']*",
                re.IGNORECASE
            ),
            # Pattern 2: Simple feet format "12' x 10'" or "12'-0" x 10'-0""
            re.compile(
                r"(\d+)\s*['\'\`\Â´]+\s*[-â€“â€”]?\s*\d*\s*[\"\"\'\']*\s*[xXÃ—\*]\s*(\d+)\s*['\'\`\Â´]+\s*[-â€“â€”]?\s*\d*\s*[\"\"\'\']*",
                re.IGNORECASE
            ),
            # Pattern 3: Simple format "12x10" or "12 x 10" with optional units
            re.compile(
                r"(\d+\.?\d*)\s*[xXÃ—\*]\s*(\d+\.?\d*)",
                re.IGNORECASE
            ),
            # Pattern 4: Dimension fragments that can appear split: number + x + number
            re.compile(
                r"(\d+)\s*['\"\'\"\`\Â´]*\s*[-â€“â€”]?\s*\d*\s*['\"\'\"\`\Â´]*\s+[xXÃ—\*]\s+(\d+)\s*['\"\'\"\`\Â´]*",
                re.IGNORECASE
            ),
        ]
        
        # Single "working" dimension pattern for classification (broad match)
        self.dimension_pattern = re.compile(
            r"\d+\s*['\"\'\"\`\Â´]*\s*[-â€“â€”]?\s*\d*\s*['\"\'\"\`\Â´]*\s*[xXÃ—\*]",
            re.IGNORECASE
        )
        
        # Area pattern (e.g., "120 sq.ft", "11.15 sqm")
        self.area_pattern = re.compile(
            r"(\d+\.?\d*)\s*(sq\.?\s*ft|sqft|sq\.?\s*m|sqm|mÂ²|ftÂ²|sft)",
            re.IGNORECASE
        )
        
        # Ignored text (Noise filter) - single chars, codes like MD, W1, D1, UP, DN, watermarks
        self.ignore_pattern = re.compile(
            r"^(up|dn|md|w\d+|d\d+|c\d*|gate|\d+|\d+['\"]|\d+['\"]\s*-?\s*\d*['\"]?|[xX]|indianplans|indian|plans|www|http|com|org|net)$",
            re.IGNORECASE
        )
                
        # Watermark keywords for content-based filtering
        self.watermark_keywords = re.compile(
            r"(indianplans|www\.|http|\.com|\.org|\.net|\.in|@|copyright)",
            re.IGNORECASE
        )
                
        # Maximum text rotation angle (degrees) for valid floor plan text
        self.max_text_rotation_deg = 15.0
        
        # Common room name keywords (for better label extraction)
        self.room_keywords = re.compile(
            r"(bed|room|bath|kitchen|living|dining|hall|toilet|wc|store|balcony|sit\s*out|"
            r"master|guest|common|pooja|puja|utility|lobby|passage|foyer|drawing|study|"
            r"office|garage|car|park|terrace|garden|court|verandah|veranda|porch|entry|"
            r"dress|closet|wardrobe|pantry|laundry|wash|dry|area|space|lounge|family|"
            r"breakfast|nook|den|library|gym|exercise|home\s*theater|theatre|media|"
            r"servant|maid|staff|driver|guard|security|reception|waiting|stair|lift|"
            r"elevator|shaft|duct|a/?c|ac\s*ledge|ledge|deck|pool|spa|sauna)",
            re.IGNORECASE
        )

        # Class-aware side-length sanity windows (in feet) for OCR validation.
        self.class_dimension_ranges: Dict[str, Tuple[float, float]] = {
            "toilet": (2.5, 12.5),
            "pooja_room": (2.0, 10.0),
            "pooja": (2.0, 10.0),
            "kitchen": (5.0, 22.0),
            "hall": (7.0, 40.0),
            "living": (7.0, 40.0),
            "bedroom": (7.0, 30.0),
            "master_bedroom": (8.0, 35.0),
            "dining": (6.0, 25.0),
        }

        # Room label typo cleanup for common OCR mistakes.
        self.label_word_map: Dict[str, str] = {
            "kilchen": "Kitchen",
            "kitcken": "Kitchen",
            "kltchen": "Kitchen",
            "dinlng": "Dining",
            "diningg": "Dining",
            "toikt": "Toilet",
            "tolet": "Toilet",
            "tcilet": "Toilet",
            "totet": "Toilet",
            "talet": "Toilet",
            "poojaa": "Pooja",
            "pocja": "Pooja",
            "puja": "Pooja",
            "bedrrom": "Bedroom",
            "bedrom": "Bedroom",
            "rlaster": "Master",
            "hlaser": "Master",
        }

        # Trigger token-based re-parse for low-confidence dimensions.
        self.low_conf_dimension_threshold = 0.60
        
        # Per-room OCR configuration defaults
        self.room_crop_pad = 20  # padding around room bbox for cropping
        self.per_room_ocr_scale = 4.0  # higher scale for small room crops
        
        # =====================================================================
        # DIMENSION OCR CONFIGURATION (specialized for small text like feet/inches)
        # =====================================================================
        self.dimension_mode = "per_room"  # "per_room" or "global"
        self.dimension_upscale = 4.0  # Upscale factor for dimension OCR
        self.dimension_room_pad = 30  # Padding around room for dimension crop
        self.dimension_use_mask = True  # Mask outside room polygon
        self.dimension_allowlist = "0123456789'\"/.-xX× "  # Characters for dimension OCR
        self.dimension_two_pass_preprocess = True  # Use both pass A and pass B
        self.debug_save_room_crops = False  # Save debug crops
        self.debug_max_crops = 10  # Max number of debug crops to save
        
        # Roboflow DocTR OCR client (lazy init)
        self._roboflow_client = None
        
        print("[INFO] FloorPlanAnalyzer initialized successfully")
    
    # =========================================================================
    # ROBOFLOW DOCTR OCR CLIENT
    # =========================================================================
    
    def _get_roboflow_client(self):
        """Get or create Roboflow inference client."""
        if self._roboflow_client is None and ROBOFLOW_SDK_AVAILABLE:
            self._roboflow_client = InferenceHTTPClient(
                api_url="https://infer.roboflow.com",
                api_key=ROBOFLOW_API_KEY
            )
        return self._roboflow_client
    
    def roboflow_doctr_ocr_text(
        self,
        image_bgr: np.ndarray,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> str:
        """
        Send image to Roboflow hosted DocTR OCR and return extracted text.
        
        Args:
            image_bgr: BGR image (numpy array)
            max_retries: Number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
        
        Returns:
            Extracted text string (empty if failed)
        """
        # Encode image as JPEG base64
        success, encoded = cv2.imencode('.jpg', image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not success:
            print("[WARN] Failed to encode image for Roboflow OCR")
            return ""
        
        image_b64 = base64.b64encode(encoded.tobytes()).decode('utf-8')
        
        # Try SDK first if available
        client = self._get_roboflow_client()
        if client is not None:
            for attempt in range(max_retries):
                try:
                    # SDK approach
                    result = client.ocr_image(inference_input=image_bgr)
                    if result and "result" in result:
                        return str(result["result"])
                    elif result and isinstance(result, dict):
                        # Try alternative response formats
                        for key in ["text", "ocr_text", "output"]:
                            if key in result:
                                return str(result[key])
                    return ""
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                    else:
                        print(f"[WARN] Roboflow SDK OCR failed: {e}")
        
        # HTTP fallback
        url = f"https://infer.roboflow.com/doctr/ocr?api_key={ROBOFLOW_API_KEY}"
        payload = {
            "image": {
                "type": "base64",
                "value": image_b64
            }
        }
        
        for attempt in range(max_retries):
            try:
                # Try GET first (some endpoints prefer it)
                response = requests.request(
                    "POST", url,
                    json=payload,
                    timeout=60,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Extract text from response
                    if "result" in data:
                        return str(data["result"])
                    elif "text" in data:
                        return str(data["text"])
                    elif "ocr_text" in data:
                        return str(data["ocr_text"])
                    # If response is just text
                    if isinstance(data, str):
                        return data
                    return ""
                else:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                    else:
                        print(f"[WARN] Roboflow HTTP OCR failed: {response.status_code} - {response.text[:200]}")
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                else:
                    print(f"[WARN] Roboflow HTTP OCR exception: {e}")
        
        return ""
    
    def crop_room_masked(
        self,
        page_img: np.ndarray,
        room_polygon: Polygon,
        pad_px: int = 40,
        upscale: float = 1.0,
    ) -> Tuple[np.ndarray, int, int]:
        """
        Crop room region from image with polygon masking.
        
        Args:
            page_img: Full page image (BGR)
            room_polygon: Room polygon in image coordinates
            pad_px: Padding around polygon bounds
            upscale: Optional upscale factor for the crop
        
        Returns:
            Tuple of (masked_crop, offset_x, offset_y)
        """
        img_h, img_w = page_img.shape[:2]
        
        # Get polygon bounds
        minx, miny, maxx, maxy = room_polygon.bounds
        
        # Apply padding and clamp
        crop_x1 = max(0, int(minx) - pad_px)
        crop_y1 = max(0, int(miny) - pad_px)
        crop_x2 = min(img_w, int(maxx) + pad_px)
        crop_y2 = min(img_h, int(maxy) + pad_px)
        
        if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
            return np.zeros((1, 1, 3), dtype=np.uint8), 0, 0
        
        # Crop image
        crop = page_img[crop_y1:crop_y2, crop_x1:crop_x2].copy()
        crop_h, crop_w = crop.shape[:2]
        
        # Create mask
        mask = np.zeros((crop_h, crop_w), dtype=np.uint8)
        
        # Shift polygon to crop coordinates
        poly_coords = np.array(room_polygon.exterior.coords, dtype=np.float32)
        poly_shifted = poly_coords - np.array([crop_x1, crop_y1])
        poly_shifted = poly_shifted.astype(np.int32)
        
        # Fill polygon area
        cv2.fillPoly(mask, [poly_shifted], 255)
        
        # Apply mask: pixels outside polygon become white
        crop_masked = crop.copy()
        crop_masked[mask == 0] = (255, 255, 255)
        
        # Upscale if requested
        if upscale > 1.0:
            new_w = int(crop_w * upscale)
            new_h = int(crop_h * upscale)
            crop_masked = cv2.resize(crop_masked, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        return crop_masked, crop_x1, crop_y1
    
    def _normalize_fraction_spacing(self, text: str) -> str:
        """
        Fix fraction spacing after Unicode glyph replacement.
        
        Converts "41/2" to "4 1/2" when the digit before fraction
        is likely a base number, not part of the fraction.
        """
        # Fix spacing for common fractions after Unicode replacement
        # e.g., "4½" -> "41/2" should become "4 1/2"
        text = re.sub(r"(\d)1/2", r"\1 1/2", text)
        text = re.sub(r"(\d)1/4", r"\1 1/4", text)
        text = re.sub(r"(\d)3/4", r"\1 3/4", text)
        text = re.sub(r"(\d)1/8", r"\1 1/8", text)
        text = re.sub(r"(\d)3/8", r"\1 3/8", text)
        text = re.sub(r"(\d)5/8", r"\1 5/8", text)
        text = re.sub(r"(\d)7/8", r"\1 7/8", text)
        return text
    
    def extract_text_roboflow_per_room(
        self,
        page_img_ocr: np.ndarray,
        rooms: List[DetectedRoom],
        scale_yolo_to_ocr: float = 1.0,
        crop_pad: int = 40,
        crop_upscale: float = 2.0,
        debug_save_crops: bool = False,
        debug_dir: Optional[Path] = None,
    ) -> List[Dict]:
        """
        Extract text for each room using Roboflow DocTR OCR on cropped regions.
        
        Args:
            page_img_ocr: High-DPI rendered page image for OCR
            rooms: Detected rooms (polygons in YOLO DPI space)
            scale_yolo_to_ocr: Scale factor from YOLO DPI to OCR DPI
            crop_pad: Padding around room bounds
            crop_upscale: Upscale factor for crop before OCR
            debug_save_crops: Save debug crop images
            debug_dir: Directory for debug outputs
        
        Returns:
            List of dicts with room_idx, text_blob, parsed_dim, parsed_label
        """
        results = []
        
        print(f"[Roboflow OCR] Processing {len(rooms)} room(s)...")
        
        for room_idx, room in enumerate(rooms):
            # Scale polygon from YOLO DPI to OCR DPI
            if scale_yolo_to_ocr != 1.0:
                room_polygon_ocr = affinity.scale(
                    room.polygon,
                    xfact=scale_yolo_to_ocr,
                    yfact=scale_yolo_to_ocr,
                    origin=(0, 0)
                )
            else:
                room_polygon_ocr = room.polygon
            
            # Crop and mask
            crop_masked, offset_x, offset_y = self.crop_room_masked(
                page_img_ocr,
                room_polygon_ocr,
                pad_px=crop_pad,
                upscale=crop_upscale,
            )
            
            if crop_masked.size < 100:
                results.append({
                    "room_idx": room_idx,
                    "text_blob": "",
                    "parsed_dim": None,
                    "parsed_label": None,
                })
                continue
            
            # Save debug crop if requested
            if debug_save_crops and debug_dir:
                debug_dir = Path(debug_dir)
                debug_dir.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(debug_dir / f"room_{room_idx:02d}_crop.png"), crop_masked)
            
            # Call Roboflow DocTR OCR
            text_blob = self.roboflow_doctr_ocr_text(crop_masked)
            
            # Normalize text
            normalized = self._normalize_ocr_text(text_blob)
            normalized = self._normalize_fraction_spacing(normalized)
            
            # Parse dimensions
            parsed_dim = None
            remaining_text = normalized
            dim_result, remaining = self._extract_dimension_from_blob(normalized)
            if dim_result:
                dim_result = self._canonicalize_dimension_text(dim_result)
                valid, conf = self._dimension_quality_score(room.class_name, dim_result)
                if valid:
                    parsed_dim = dim_result
                    remaining_text = remaining
            
            # Parse label
            parsed_label = self._clean_label(remaining_text)
            if not parsed_label:
                parsed_label = room.class_name.replace("_", " ").title()
            
            results.append({
                "room_idx": room_idx,
                "text_blob": text_blob,
                "normalized_text": normalized,
                "parsed_dim": parsed_dim,
                "parsed_label": parsed_label,
            })
            
            if parsed_dim:
                print(f"  [Room {room_idx+1}] Dim: {parsed_dim}, Label: {parsed_label}")
            else:
                print(f"  [Room {room_idx+1}] Label: {parsed_label} (no dimension)")
        
        return results
    
    # =========================================================================
    # DIMENSION-SPECIFIC OCR (2-pass preprocessing + allowlist)
    # =========================================================================
    
    def preprocess_for_dimensions(self, crop_img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create two preprocessing variants optimized for dimension text.
        
        PASS A (no threshold): Preserves thin strokes like ', ", /
        - Grayscale → CLAHE → Mild sharpen
        
        PASS B (threshold + stroke thickening): Better for very faint text
        - Grayscale → Adaptive threshold → Light dilation
        
        Args:
            crop_img: BGR image (room crop)
        
        Returns:
            Tuple of (pass_a_img, pass_b_img) both as BGR
        """
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
        
        # =================================================================
        # PASS A: No binarization (keeps thin punctuation)
        # =================================================================
        # CLAHE for local contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        pass_a = clahe.apply(gray)
        
        # Mild sharpen using unsharp mask
        blurred = cv2.GaussianBlur(pass_a, (0, 0), 2.0)
        pass_a = cv2.addWeighted(pass_a, 1.5, blurred, -0.5, 0)
        
        # Convert back to BGR for OCR
        pass_a_bgr = cv2.cvtColor(pass_a, cv2.COLOR_GRAY2BGR)
        
        # =================================================================
        # PASS B: Threshold + stroke thickening (mimics blur effect)
        # =================================================================
        # Adaptive threshold
        pass_b = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Invert so text is white on black (for dilation to thicken strokes)
        pass_b = cv2.bitwise_not(pass_b)
        
        # Light dilation to thicken thin strokes like ', ", /
        kernel = np.ones((2, 2), np.uint8)
        pass_b = cv2.dilate(pass_b, kernel, iterations=1)
        
        # Invert back to black text on white
        pass_b = cv2.bitwise_not(pass_b)
        
        # Convert back to BGR for OCR
        pass_b_bgr = cv2.cvtColor(pass_b, cv2.COLOR_GRAY2BGR)
        
        return pass_a_bgr, pass_b_bgr
    
    def _is_dimension_text(self, text: str) -> bool:
        """
        Check if text looks like a dimension (has digits + dimension symbols).
        
        Dimensions MUST have: at least one digit AND at least one of: ' " x / -
        This prevents label text from polluting dimension results.
        """
        text = text.strip()
        if not text:
            return False
        
        has_digit = bool(re.search(r'\d', text))
        has_dim_symbol = bool(re.search(r"['\"/x\-]", text, re.IGNORECASE))
        
        return has_digit and has_dim_symbol
    
    def _merge_ocr_detections(
        self,
        detections_a: List[Tuple],
        detections_b: List[Tuple],
        iou_threshold: float = 0.5
    ) -> List[Tuple]:
        """
        Merge OCR detections from two passes, keeping higher confidence.
        
        Args:
            detections_a: Results from pass A [(bbox, text, conf), ...]
            detections_b: Results from pass B [(bbox, text, conf), ...]
            iou_threshold: IoU threshold for considering duplicates
        
        Returns:
            Merged list of detections
        """
        all_dets = list(detections_a) + list(detections_b)
        if not all_dets:
            return []
        
        # Group by normalized text + approximate position
        merged = {}
        for det in all_dets:
            bbox, text, conf = det
            
            # Compute center of bbox
            pts = np.array(bbox)
            cx = pts[:, 0].mean()
            cy = pts[:, 1].mean()
            
            # Create key from approximate position and normalized text
            norm_text = self._normalize_ocr_text(text).lower()
            key = (int(cx / 20), int(cy / 20), norm_text)
            
            existing = merged.get(key)
            if existing is None or conf > existing[2]:
                merged[key] = det
        
        return list(merged.values())
    
    def extract_dimensions_per_room(
        self,
        page_img_ocr: np.ndarray,
        rooms: List[DetectedRoom],
        scale_yolo_to_ocr: float = 1.0,
        upscale: float = None,
        room_pad: int = None,
        use_mask: bool = None,
        two_pass: bool = None,
        allowlist: str = None,
        debug_save: bool = None,
        debug_dir: Optional[Path] = None,
    ) -> Dict[int, str]:
        """
        Extract DIMENSIONS from each room using specialized OCR.
        
        This uses a restricted allowlist and 2-pass preprocessing
        optimized for small dimension text (feet, inches, fractions).
        
        Args:
            page_img_ocr: High-DPI image for OCR
            rooms: Detected rooms (polygons in YOLO DPI space)
            scale_yolo_to_ocr: Scale factor from YOLO to OCR space
            upscale: Upscale factor for crop (default: self.dimension_upscale)
            room_pad: Padding around room (default: self.dimension_room_pad)
            use_mask: Mask outside polygon (default: self.dimension_use_mask)
            two_pass: Use 2-pass preprocessing (default: self.dimension_two_pass_preprocess)
            allowlist: Characters for dimension OCR (default: self.dimension_allowlist)
            debug_save: Save debug crops (default: self.debug_save_room_crops)
            debug_dir: Directory for debug outputs
        
        Returns:
            Dict mapping room_idx to dimension text blob
        """
        # Use defaults from instance if not provided
        upscale = upscale if upscale is not None else self.dimension_upscale
        room_pad = room_pad if room_pad is not None else self.dimension_room_pad
        use_mask = use_mask if use_mask is not None else self.dimension_use_mask
        two_pass = two_pass if two_pass is not None else self.dimension_two_pass_preprocess
        allowlist = allowlist if allowlist is not None else self.dimension_allowlist
        debug_save = debug_save if debug_save is not None else self.debug_save_room_crops
        
        print(f"[Dimension OCR] Processing {len(rooms)} room(s) with specialized extraction...")
        
        dimension_blobs: Dict[int, str] = {}
        saved_crops = 0
        
        for room_idx, room in enumerate(rooms):
            # Scale polygon from YOLO DPI to OCR DPI
            if scale_yolo_to_ocr != 1.0:
                room_polygon_ocr = affinity.scale(
                    room.polygon,
                    xfact=scale_yolo_to_ocr,
                    yfact=scale_yolo_to_ocr,
                    origin=(0, 0)
                )
            else:
                room_polygon_ocr = room.polygon
            
            # Get polygon bounds for cropping
            minx, miny, maxx, maxy = room_polygon_ocr.bounds
            img_h, img_w = page_img_ocr.shape[:2]
            
            # Apply padding and clamp
            crop_x1 = max(0, int(minx) - room_pad)
            crop_y1 = max(0, int(miny) - room_pad)
            crop_x2 = min(img_w, int(maxx) + room_pad)
            crop_y2 = min(img_h, int(maxy) + room_pad)
            
            if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                dimension_blobs[room_idx] = ""
                continue
            
            # Crop image
            crop = page_img_ocr[crop_y1:crop_y2, crop_x1:crop_x2].copy()
            
            # Apply polygon mask if enabled
            if use_mask:
                mask = np.zeros((crop.shape[0], crop.shape[1]), dtype=np.uint8)
                poly_coords = np.array(room_polygon_ocr.exterior.coords, dtype=np.float32)
                poly_shifted = poly_coords - np.array([crop_x1, crop_y1])
                poly_shifted = poly_shifted.astype(np.int32)
                cv2.fillPoly(mask, [poly_shifted], 255)
                crop[mask == 0] = (255, 255, 255)
            
            # Upscale crop
            if upscale > 1.0:
                new_w = int(crop.shape[1] * upscale)
                new_h = int(crop.shape[0] * upscale)
                crop = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            
            # Create preprocessing passes
            if two_pass:
                pass_a, pass_b = self.preprocess_for_dimensions(crop)
            else:
                pass_a = crop
                pass_b = None
            
            # Save debug crops if enabled
            if debug_save and debug_dir and saved_crops < self.debug_max_crops:
                debug_dir = Path(debug_dir)
                debug_dir.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(debug_dir / f"room_{room_idx:02d}_crop_masked.png"), crop)
                cv2.imwrite(str(debug_dir / f"room_{room_idx:02d}_pass_a.png"), pass_a)
                if pass_b is not None:
                    cv2.imwrite(str(debug_dir / f"room_{room_idx:02d}_pass_b.png"), pass_b)
                saved_crops += 1
            
            # Run OCR on pass A with allowlist
            try:
                detections_a = self.ocr_reader.readtext(
                    pass_a,
                    allowlist=allowlist,
                    decoder='beamsearch',
                    text_threshold=0.3,
                    low_text=0.3,
                    link_threshold=0.2,
                )
            except Exception as e:
                print(f"  [WARN] Pass A OCR failed for room {room_idx}: {e}")
                detections_a = []
            
            # Run OCR on pass B if enabled
            detections_b = []
            if two_pass and pass_b is not None:
                try:
                    detections_b = self.ocr_reader.readtext(
                        pass_b,
                        allowlist=allowlist,
                        decoder='beamsearch',
                        text_threshold=0.3,
                        low_text=0.3,
                        link_threshold=0.2,
                    )
                except Exception as e:
                    print(f"  [WARN] Pass B OCR failed for room {room_idx}: {e}")
            
            # Merge detections from both passes
            merged_dets = self._merge_ocr_detections(detections_a, detections_b)
            
            # Filter to keep only dimension-like text
            dim_texts = []
            for bbox, text, conf in merged_dets:
                norm_text = self._normalize_ocr_text(text)
                norm_text = self._normalize_fraction_spacing(norm_text)
                if self._is_dimension_text(norm_text):
                    # Get center Y for sorting
                    pts = np.array(bbox)
                    cy = pts[:, 1].mean()
                    cx = pts[:, 0].mean()
                    dim_texts.append((cy, cx, norm_text, conf))
            
            # Sort by Y then X (reading order)
            dim_texts.sort(key=lambda x: (x[0], x[1]))
            
            # Join into dimension blob
            dim_blob = " ".join([t[2] for t in dim_texts])
            dimension_blobs[room_idx] = dim_blob
            
            if dim_blob:
                print(f"  [Room {room_idx+1}] Dimension text: {dim_blob[:50]}..." if len(dim_blob) > 50 else f"  [Room {room_idx+1}] Dimension text: {dim_blob}")
        
        return dimension_blobs
    
    def extract_labels_global(
        self,
        page_img: np.ndarray,
        rooms: List[DetectedRoom],
        conf_threshold: float = 0.3,
        filter_watermarks: bool = True,
    ) -> Dict[int, str]:
        """
        Extract LABELS (room names) using global OCR without allowlist.
        
        This path is optimized for words/room names, NOT dimensions.
        Uses standard OCR without character restrictions.
        
        Args:
            page_img: Page image
            rooms: Detected rooms
            conf_threshold: OCR confidence threshold
            filter_watermarks: Filter diagonal/watermark text
        
        Returns:
            Dict mapping room_idx to label text
        """
        print("[Label OCR] Running global OCR for room labels...")
        
        # Run global OCR without allowlist (optimized for words)
        try:
            results = self.ocr_reader.readtext(
                page_img,
                text_threshold=0.4,
                low_text=0.4,
                paragraph=False,
            )
        except Exception as e:
            print(f"[WARN] Global label OCR failed: {e}")
            return {}
        
        # Create TextRegions from results
        text_regions = []
        for bbox_pts, text, conf in results:
            if conf < conf_threshold:
                continue
            
            # Check for watermarks
            if filter_watermarks:
                rotation = self._compute_text_rotation(bbox_pts)
                if self._is_watermark_text(text, rotation):
                    continue
            
            # Skip if looks like dimension (we handle those separately)
            if self._is_dimension_text(text):
                continue
            
            # Skip ignored patterns
            if self.ignore_pattern.match(text.strip()):
                continue
            
            pts = np.array(bbox_pts)
            x1, y1 = pts.min(axis=0)
            x2, y2 = pts.max(axis=0)
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            
            text_regions.append(TextRegion(
                text=text.strip(),
                bbox=(int(x1), int(y1), int(x2), int(y2)),
                center=(cx, cy),
                confidence=conf,
                text_type="label"
            ))
        
        # Map labels to rooms using point-in-polygon
        room_labels: Dict[int, str] = {}
        
        for room_idx, room in enumerate(rooms):
            room_texts = []
            for tr in text_regions:
                point = Point(tr.center)
                if room.polygon.contains(point):
                    room_texts.append(tr.text)
            
            if room_texts:
                # Join texts and clean
                combined = " ".join(room_texts)
                cleaned = self._clean_label(combined)
                if cleaned:
                    room_labels[room_idx] = cleaned
        
        return room_labels
    
    # =========================================================================
    # STEP 1: YOLO Room Detection
    # =========================================================================
    
    def detect_rooms(
        self,
        image: Union[str, Path, np.ndarray],
        conf_threshold: float = 0.4
    ) -> List[DetectedRoom]:
        """
        Detect rooms using YOLOv8 instance segmentation.
        
        Args:
            image: Image path or numpy array
            conf_threshold: Confidence threshold (0-1)
        
        Returns:
            List of DetectedRoom objects with Shapely polygons
        """
        # Load image if path provided
        if isinstance(image, (str, Path)):
            image = cv2.imread(str(image))
            if image is None:
                raise ValueError(f"Failed to read image")
        
        # Run YOLO prediction
        results = self.yolo_model.predict(
            source=image,
            conf=conf_threshold,
            save=False,
            verbose=False
        )
        
        result = results[0]
        
        if result.masks is None:
            print("[WARN] No rooms detected")
            return []
        
        detected_rooms: List[DetectedRoom] = []
        class_names = result.names
        
        for i in range(len(result.masks.xy)):
            mask_points = result.masks.xy[i]
            
            if len(mask_points) < 3:
                continue
            
            # Convert to Shapely Polygon
            try:
                polygon = Polygon(mask_points)
                if not polygon.is_valid:
                    polygon = make_valid(polygon)
                    if polygon.geom_type == 'MultiPolygon':
                        polygon = max(polygon.geoms, key=lambda p: p.area)
                    elif polygon.geom_type != 'Polygon':
                        continue
                
                if polygon.area < 100:
                    continue
                    
            except Exception as e:
                print(f"[WARN] Polygon creation failed: {e}")
                continue
            
            class_id = int(result.boxes.cls[i])
            class_name = class_names[class_id]
            confidence = float(result.boxes.conf[i])
            box = result.boxes.xyxy[i].cpu().numpy()
            bbox = tuple(map(int, box))
            
            room = DetectedRoom(
                polygon=polygon,
                class_name=class_name,
                confidence=confidence,
                bbox=bbox,
                area_pixels=polygon.area,
                mask_points=mask_points
            )
            detected_rooms.append(room)
        
        print(f"[INFO] Detected {len(detected_rooms)} room(s)")
        return detected_rooms

    @staticmethod
    def _rect_to_int_bbox(rect: fitz.Rect, width_px: int, height_px: int) -> Tuple[int, int, int, int]:
        """
        Convert a float Rect to a clamped integer bbox in rendered image pixel space.
        """
        x1 = int(np.floor(rect.x0))
        y1 = int(np.floor(rect.y0))
        x2 = int(np.ceil(rect.x1))
        y2 = int(np.ceil(rect.y1))

        x1 = max(0, min(x1, max(0, width_px - 1)))
        y1 = max(0, min(y1, max(0, height_px - 1)))
        x2 = max(0, min(x2, max(0, width_px - 1)))
        y2 = max(0, min(y2, max(0, height_px - 1)))

        if x2 <= x1:
            x2 = min(max(0, width_px - 1), x1 + 1)
        if y2 <= y1:
            y2 = min(max(0, height_px - 1), y1 + 1)
        return x1, y1, x2, y2

    def _open_pdf(self, pdf_path: Union[str, Path]) -> "fitz.Document":
        """Open a PDF file and return a live fitz.Document handle."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        return fitz.open(str(pdf_path))

    def _pdf_page_has_text_layer(self, page: "fitz.Page", min_words: int = 10) -> bool:
        """
        Check if a PDF page has a real text layer (not scanned).
        
        Args:
            page: PyMuPDF page object
            min_words: Minimum word count to consider as having text layer
        
        Returns:
            True if page has usable text layer, False if scanned/image-only
        """
        words = page.get_text("words") or []
        if len(words) < min_words:
            return False
        
        # Additional heuristic: count words that look like floor plan content
        # (letters, dimension patterns, room names)
        useful_count = 0
        for word in words:
            if len(word) < 5:
                continue
            text = str(word[4]).strip()
            if not text:
                continue
            # Has letters (room names) or dimension-like patterns
            has_letters = bool(re.search(r'[a-zA-Z]', text))
            has_dimension = bool(re.search(r"\d+['\"-]", text)) or 'x' in text.lower()
            if has_letters or has_dimension:
                useful_count += 1
        
        # At least 30% of words should be useful floor plan content
        return useful_count >= max(5, len(words) * 0.3)

    def _compute_text_rotation(self, bbox_points: List[Tuple[float, float]]) -> float:
        """
        Compute rotation angle of text from OCR bbox points.
        
        Args:
            bbox_points: 4 corner points from EasyOCR [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
        
        Returns:
            Rotation angle in degrees (0 = horizontal)
        """
        if len(bbox_points) < 2:
            return 0.0
        # Top edge: from point 0 to point 1
        x1, y1 = bbox_points[0]
        x2, y2 = bbox_points[1]
        dx = x2 - x1
        dy = y2 - y1
        angle_rad = np.arctan2(dy, dx)
        angle_deg = np.degrees(angle_rad)
        return angle_deg

    def _is_watermark_text(self, text: str, rotation_deg: float = 0.0) -> bool:
        """
        Check if text is likely a watermark.
        
        Args:
            text: The OCR text
            rotation_deg: Text rotation angle in degrees
        
        Returns:
            True if text appears to be a watermark
        """
        normalized = self._normalize_ocr_text(text).lower()
        
        # Content-based check
        if self.watermark_keywords.search(normalized):
            return True
        
        # Rotation-based check (watermarks are often diagonal)
        # But only if text doesn't look like a dimension
        is_dimension = bool(self.dimension_pattern.search(text))
        if not is_dimension and abs(rotation_deg) > self.max_text_rotation_deg:
            return True
        
        return False

    def _render_pdf_page(
        self,
        pdf_path: Union[str, Path],
        page_index: int,
        dpi: int = 300,
        doc: Optional["fitz.Document"] = None,
    ) -> Tuple[np.ndarray, "fitz.Page", PDFRenderContext]:
        """
        Render one PDF page into BGR image for YOLO and return rendering context.
        """
        local_doc = doc
        if local_doc is None:
            local_doc = self._open_pdf(pdf_path)
            # Keep reference alive if caller did not provide a shared document.
            self._last_pdf_doc = local_doc

        page = local_doc.load_page(page_index)
        zoom = float(dpi) / 72.0
        mat = fitz.Matrix(zoom, zoom).prerotate(page.rotation)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            image_bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            image_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        elif pix.n == 1:
            image_bgr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        else:
            # Fallback for uncommon channel formats.
            image_bgr = arr[:, :, :3].copy()

        ctx = PDFRenderContext(
            dpi=int(dpi),
            zoom=zoom,
            matrix=mat,
            rotation=int(page.rotation),
            width_px=int(pix.width),
            height_px=int(pix.height),
        )
        return image_bgr, page, ctx

    def extract_text_from_pdf_page(
        self,
        page: "fitz.Page",
        ctx: PDFRenderContext,
        conf_threshold: float = 0.0
    ) -> List[TextRegion]:
        """
        Extract text tokens from a PDF text layer and map them to rendered pixel coordinates.
        """
        words = page.get_text("words") or []
        if not words:
            return []

        text_regions: List[TextRegion] = []
        for word in words:
            if len(word) < 5:
                continue
            raw_text = str(word[4]).strip()
            if not raw_text:
                continue

            rect_pt = fitz.Rect(float(word[0]), float(word[1]), float(word[2]), float(word[3]))
            rect_px = rect_pt * ctx.matrix
            x1, y1, x2, y2 = self._rect_to_int_bbox(rect_px, ctx.width_px, ctx.height_px)

            normalized_text = self._normalize_ocr_text(raw_text)
            if not normalized_text:
                continue

            confidence = 1.0
            if confidence < conf_threshold:
                continue

            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            text_regions.append(
                TextRegion(
                    text=normalized_text,
                    bbox=(x1, y1, x2, y2),
                    center=(cx, cy),
                    confidence=confidence,
                    text_type=self._classify_text(normalized_text),
                )
            )
        return text_regions

    def debug_draw_pdf_word_boxes(
        self,
        page_img: np.ndarray,
        text_regions: List[TextRegion],
        out_path: Union[str, Path],
        n: int = 50
    ) -> None:
        """
        Draw the first N PDF text tokens with boxes for coordinate mapping validation.
        """
        vis = page_img.copy()
        for tr in text_regions[:max(0, int(n))]:
            x1, y1, x2, y2 = tr.bbox
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 1)
            cv2.putText(
                vis,
                tr.text[:24],
                (x1, max(8, y1 - 2)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 0, 255),
                1,
                cv2.LINE_AA,
            )
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), vis)
    
    # =========================================================================
    # STEP 2: EasyOCR Text Extraction (with Preprocessing)
    # =========================================================================
    
    def preprocess_for_ocr(
        self,
        image: np.ndarray,
        scale_factor: float = 2.0
    ) -> Tuple[np.ndarray, float]:
        """
        Preprocess image to improve OCR accuracy on floor plan text.
        
        Pipeline:
            1. Upscale: Resize to 2x/3x (EasyOCR works better on larger text)
            2. Grayscale: Convert to single channel
            3. Threshold: Binary threshold to make text bold black on white
            4. Denoise: Optional median blur to reduce noise
        
        Args:
            image: Original BGR image (numpy array)
            scale_factor: How much to upscale (2.0 = 2x, 3.0 = 3x)
        
        Returns:
            Tuple of (processed_image, scale_factor_used)
        """
        # Keep OCR preprocessing isolated from YOLO image usage.
        clean = image.copy()

        # 1. UPSCALE: enlarge tiny room labels before OCR.
        h, w = clean.shape[:2]
        safe_scale = max(1.0, float(scale_factor))
        new_w = int(w * safe_scale)
        new_h = int(h * safe_scale)
        upscaled = cv2.resize(clean, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        print(f"[OCR Preprocess] Upscaled: {w}x{h} -> {new_w}x{new_h} ({safe_scale:.2f}x)")

        # 2. GRAYSCALE + local contrast boost for faint text strokes.
        gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)

        # 3. SHARPEN: recover character edges after resize.
        blurred = cv2.GaussianBlur(contrast, (0, 0), sigmaX=1.0, sigmaY=1.0)
        sharpened = cv2.addWeighted(contrast, 1.7, blurred, -0.7, 0)

        # 4. BINARIZE: strong black/white text for EasyOCR.
        adaptive = cv2.adaptiveThreshold(
            sharpened,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=8
        )
        _, otsu = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Pick the cleaner candidate (fewer connected foreground pixels generally
        # means less background noise for floor plans with thin text).
        adaptive_fg = np.count_nonzero(adaptive == 0)
        otsu_fg = np.count_nonzero(otsu == 0)
        binary = adaptive if adaptive_fg <= otsu_fg else otsu

        # 5. LIGHT DENOISE while preserving glyph structure.
        denoised = cv2.medianBlur(binary, 3)

        # EasyOCR accepts 3-channel images; keep output BGR.
        processed = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
        print("[OCR Preprocess] Applied: CLAHE -> Sharpen -> Threshold -> Denoise")

        return processed, safe_scale
    
    def extract_text(
        self,
        image: Union[str, Path, np.ndarray],
        conf_threshold: float = 0.3,
        use_preprocessing: bool = True,
        ocr_scale_factor: float = 2.0
    ) -> List[TextRegion]:
        """
        Extract text from image using EasyOCR with optional preprocessing.
        
        Args:
            image: Image path or numpy array
            conf_threshold: OCR confidence threshold
            use_preprocessing: Whether to apply OCR preprocessing (upscale, threshold)
            ocr_scale_factor: Scale factor for preprocessing (2.0 = 2x upscale)
        
        Returns:
            List of TextRegion objects with classified text types
            (coordinates are in ORIGINAL image space, not upscaled)
        """
        # Load image if path provided
        if isinstance(image, (str, Path)):
            image = cv2.imread(str(image))
            if image is None:
                raise ValueError(f"Failed to read image")
        
        # Store original dimensions for coordinate scaling
        original_h, original_w = image.shape[:2]
        
        # Apply preprocessing if enabled
        scale_factor = 1.0  # Default: no scaling
        if use_preprocessing:
            ocr_image, scale_factor = self.preprocess_for_ocr(image, ocr_scale_factor)
        else:
            ocr_image = image
        
        # Run EasyOCR on (possibly preprocessed) image
        ocr_results = self.ocr_reader.readtext(ocr_image)
        
        text_regions: List[TextRegion] = []
        
        for detection in ocr_results:
            bbox_points, text, confidence = detection

            if not text.strip():
                continue

            # Keep likely dimension fragments even if confidence is below
            # generic text threshold. This helps when OCR splits dimensions
            # into low-confidence pieces like "14'-10}" + "X" + "7.1}".
            if confidence < conf_threshold and not self._looks_like_dimension_fragment(text):
                continue
            
            # Convert bbox points to x1,y1,x2,y2
            pts = np.array(bbox_points)
            x1, y1 = pts.min(axis=0)
            x2, y2 = pts.max(axis=0)
            
            # CRITICAL: Scale coordinates back to original image space
            # If we upscaled by 2x, coordinates are 2x larger - divide by scale_factor
            x1 = x1 / scale_factor
            y1 = y1 / scale_factor
            x2 = x2 / scale_factor
            y2 = y2 / scale_factor
            
            # Calculate center point (in original image coordinates)
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # Classify text type
            text_type = self._classify_text(text)
            
            text_region = TextRegion(
                text=text.strip(),
                bbox=(int(x1), int(y1), int(x2), int(y2)),
                center=(center_x, center_y),
                confidence=confidence,
                text_type=text_type
            )
            text_regions.append(text_region)
        
        print(f"[INFO] Extracted {len(text_regions)} text region(s) (scale_factor={scale_factor})")
        return text_regions

    def extract_text_per_room(
        self,
        page_img: np.ndarray,
        rooms: List[DetectedRoom],
        conf_threshold: float = 0.3,
        ocr_preprocess: bool = True,
        base_scale: float = 4.0,
        room_pad: int = 20,
        mask_to_polygon: bool = True,
        filter_watermarks: bool = True,
    ) -> List[TextRegion]:
        """
        Extract text per room by cropping and running OCR on each room separately.
        
        This is more effective for scanned PDFs where global OCR struggles with
        small text and watermarks.
        
        Args:
            page_img: Full page image (BGR)
            rooms: List of detected rooms with polygons
            conf_threshold: OCR confidence threshold
            ocr_preprocess: Apply preprocessing (grayscale, threshold)
            base_scale: Upscale factor for room crops (4.0 = 4x)
            room_pad: Padding around room bbox when cropping
            mask_to_polygon: Mask pixels outside polygon to white
            filter_watermarks: Filter diagonal/watermark text
        
        Returns:
            List of TextRegion in GLOBAL page coordinates
        """
        all_text_regions: List[TextRegion] = []
        img_h, img_w = page_img.shape[:2]
        
        print(f"[Per-Room OCR] Processing {len(rooms)} room(s) with scale={base_scale}")
        
        for room_idx, room in enumerate(rooms):
            # 1. Compute crop bbox with padding
            x1, y1, x2, y2 = room.bbox
            crop_x1 = max(0, x1 - room_pad)
            crop_y1 = max(0, y1 - room_pad)
            crop_x2 = min(img_w, x2 + room_pad)
            crop_y2 = min(img_h, y2 + room_pad)
            
            if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                continue
            
            # 2. Crop the image
            crop = page_img[crop_y1:crop_y2, crop_x1:crop_x2].copy()
            crop_h, crop_w = crop.shape[:2]
            
            # 3. Mask outside polygon if enabled
            if mask_to_polygon:
                # Create mask
                mask = np.zeros((crop_h, crop_w), dtype=np.uint8)
                
                # Shift polygon to crop coordinates
                poly_coords = np.array(room.polygon.exterior.coords, dtype=np.float32)
                poly_shifted = poly_coords - np.array([crop_x1, crop_y1])
                poly_shifted = poly_shifted.astype(np.int32)
                
                # Fill polygon area
                cv2.fillPoly(mask, [poly_shifted], 255)
                
                # Apply mask: pixels outside polygon become white
                crop_masked = crop.copy()
                crop_masked[mask == 0] = 255
                crop = crop_masked
            
            # 4. Run OCR with preprocessing (two passes)
            room_texts: List[TextRegion] = []
            
            # PASS A: Upscaled grayscale (no threshold)
            scale = max(1.0, base_scale)
            upscaled = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
            gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
            gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            
            ocr_results_a = self.ocr_reader.readtext(gray_bgr)
            
            # PASS B: Upscaled + adaptive threshold
            if ocr_preprocess:
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                thresh = cv2.adaptiveThreshold(
                    enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 31, 9
                )
                thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                ocr_results_b = self.ocr_reader.readtext(thresh_bgr)
            else:
                ocr_results_b = []
            
            # Combine results from both passes
            all_ocr = ocr_results_a + ocr_results_b
            
            # 5. Process OCR results and convert to global coordinates
            seen_texts: Set[Tuple[int, int, str]] = set()
            
            for detection in all_ocr:
                bbox_points, text, confidence = detection
                
                if not text.strip():
                    continue
                
                if confidence < conf_threshold and not self._looks_like_dimension_fragment(text):
                    continue
                
                # Compute rotation for watermark filtering
                rotation_deg = self._compute_text_rotation(bbox_points)
                
                # Filter watermarks
                if filter_watermarks and self._is_watermark_text(text, rotation_deg):
                    continue
                
                # Convert to crop coordinates (accounting for scale)
                pts = np.array(bbox_points)
                pts = pts / scale  # Scale back to crop space
                
                x1_local, y1_local = pts.min(axis=0)
                x2_local, y2_local = pts.max(axis=0)
                
                # Convert to global page coordinates
                x1_global = x1_local + crop_x1
                y1_global = y1_local + crop_y1
                x2_global = x2_local + crop_x1
                y2_global = y2_local + crop_y1
                
                center_x = (x1_global + x2_global) / 2
                center_y = (y1_global + y2_global) / 2
                
                # Dedupe by approximate position and text
                dedup_key = (
                    int(center_x / 10),
                    int(center_y / 10),
                    self._normalize_ocr_text(text).lower()
                )
                if dedup_key in seen_texts:
                    continue
                seen_texts.add(dedup_key)
                
                text_type = self._classify_text(text)
                
                text_region = TextRegion(
                    text=text.strip(),
                    bbox=(int(x1_global), int(y1_global), int(x2_global), int(y2_global)),
                    center=(center_x, center_y),
                    confidence=confidence,
                    text_type=text_type
                )
                room_texts.append(text_region)
            
            all_text_regions.extend(room_texts)
            
            if room_texts:
                print(f"  [Room {room_idx+1}] Found {len(room_texts)} text(s)")
        
        # Final deduplication across all rooms
        final_regions = self._dedupe_text_regions(all_text_regions)
        
        print(f"[Per-Room OCR] Total: {len(final_regions)} text region(s)")
        return final_regions

    def _dedupe_text_regions(self, regions: List[TextRegion]) -> List[TextRegion]:
        """
        Remove duplicate text regions based on position and content.
        Keep the one with higher confidence.
        """
        deduped: Dict[Tuple[int, int, str], TextRegion] = {}
        
        for tr in regions:
            key = (
                int(tr.center[0] / 8),
                int(tr.center[1] / 8),
                self._normalize_ocr_text(tr.text).lower()
            )
            existing = deduped.get(key)
            if existing is None or tr.confidence > existing.confidence:
                deduped[key] = tr
        
        return list(deduped.values())
    
    def _classify_text(self, text: str) -> str:
        """Classify text as label, dimension, or area."""
        text = text.strip()
        
        # Check for dimension pattern (e.g., "12x10", "12' x 10'")
        if self.dimension_pattern.search(text):
            return "dimension"

        # Include partial dimension tokens (e.g., "14'-10}", "7.1}", "X")
        if self._looks_like_dimension_fragment(text):
            return "dimension"
        
        # Check for area pattern (e.g., "120 sq.ft", "11.15 sqm")
        if self.area_pattern.search(text):
            return "area"
        
        # Otherwise it's a label (room name)
        return "label"

    def _looks_like_dimension_fragment(self, text: str) -> bool:
        """
        Heuristic for OCR fragments that are likely part of a dimension.
        """
        norm = self._normalize_ocr_text(text).lower()
        if not norm:
            return False

        if norm in {"x", "×", "*"}:
            return True

        has_digit = bool(re.search(r"\d", norm))
        has_dim_symbol = bool(re.search(r"[x'\"/\-:\.\]\}]", norm))
        return has_digit and has_dim_symbol
    
    # =========================================================================
    # STEP 3: Map Text to Rooms (Collect -> Sort -> Merge -> Parse)
    # =========================================================================
    
    def _normalize_ocr_text(self, text: str) -> str:
        """
        Normalize OCR text by fixing common OCR errors and standardizing characters.
        """
        replacements = {
            "Ã—": "x",
            "×": "x",
            "*": "x",
            "â€“": "-",
            "â€”": "-",
            "–": "-",
            "—": "-",
            "`": "'",
            "´": "'",
            "Â´": "'",
            "’": "'",
            "‘": "'",
            "“": '"',
            "”": '"',
            "½": "1/2",
            "¼": "1/4",
            "¾": "3/4",
            "㎡": "sqm",
            "m²": "sqm",
            "ft²": "sqft",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)

        # Normalize separator-like glyphs.
        text = text.replace("×", "x").replace("X", "x")
        text = re.sub(r"\s*x\s*", " x ", text)
        text = re.sub(r"\s*-\s*", "-", text)
        # Restore readable spacing around x after dash compaction.
        text = re.sub(r"\s*x\s*", " x ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _parse_dimension_side(self, side_text: str) -> Optional[Tuple[int, str, int]]:
        """
        Parse one side of a dimension token into feet and inches.

        Returns:
            (feet, inches_text, score) or None if parsing fails.
        """
        side = self._normalize_ocr_text(side_text)
        # OCR may render 1/2 glyph fragments as ] or } around inch values.
        side = side.replace("}", "2").replace("]", "2")
        # Keep slash for fraction parsing.
        side = re.sub(r"[^0-9'\"./\-\s]", " ", side)
        side = re.sub(r"\s+", " ", side).strip()
        if not side:
            return None

        feet_marker_match = re.search(r"(\d{1,2})\s*'", side)
        if feet_marker_match:
            feet = int(feet_marker_match.group(1))
            tail = side[feet_marker_match.end():]
            has_feet_marker = True
        else:
            feet_match = re.search(r"(\d{1,2})", side)
            if not feet_match:
                return None
            feet = int(feet_match.group(1))
            tail = side[feet_match.end():]
            has_feet_marker = False

        if feet == 0 and re.search(r"[tTiI]\s*0", side):
            feet = 7
        if not (1 <= feet <= 60):
            return None

        tail_clean = tail.replace('"', " ")

        # Parse inches + explicit fraction (e.g., 6 1/2, 6-3/4, 1/2).
        frac_match = re.search(r"(\d)\s*/\s*(\d{1,2})", tail_clean)
        if frac_match:
            num = int(frac_match.group(1))
            den = int(frac_match.group(2))
            if den in {2, 4, 8, 16} and 0 < num < den:
                prefix = tail_clean[:frac_match.start()]
                base_match = re.search(r"(\d{1,2})\s*$", prefix)
                inches = int(base_match.group(1)) if base_match else 0
                if 0 <= inches <= 11:
                    score = 6 if has_feet_marker else 4
                    return feet, f"{inches}-{num}/{den}", score

        # OCR legacy fallback: half-inch encoded as trailing 2, e.g. 72 => 7-1/2.
        inch_match = re.search(r"(\d{1,3})", tail_clean)
        if inch_match:
            inch_digits = inch_match.group(1)
            if len(inch_digits) == 2 and inch_digits.endswith("2") and int(inch_digits[0]) <= 11:
                score = 5 if has_feet_marker else 3
                return feet, f"{int(inch_digits[0])}-1/2", score
            if len(inch_digits) == 3 and inch_digits.endswith("2") and int(inch_digits[:2]) <= 11:
                score = 5 if has_feet_marker else 3
                return feet, f"{int(inch_digits[:2])}-1/2", score

            inches = int(inch_digits)
            if 0 <= inches <= 11:
                score = 4 if has_feet_marker else 3
                return feet, str(inches), score

        # Feet-only fallback.
        if 1 <= feet <= 60:
            return feet, "0", 1

        return None

    def _extract_dimension_from_blob(self, text_blob: str) -> Tuple[Optional[str], str]:
        """
        Extract dimension string from merged text blob.

        Returns:
            Tuple of (dimension_string, remaining_text)
        """
        normalized = self._normalize_ocr_text(text_blob)

        best = None
        candidate_pattern = re.compile(r"([0-9'\"./\-\]\}\s]{1,24})\s*x\s*([0-9'\"./\-\]\}\s]{1,24})")
        for match in candidate_pattern.finditer(normalized):
            left = self._parse_dimension_side(match.group(1))
            right = self._parse_dimension_side(match.group(2))
            if not left or not right:
                continue

            score = left[2] + right[2]
            if best is None or score > best["score"] or (score == best["score"] and len(match.group(0)) > len(best["raw"])):
                best = {
                    "score": score,
                    "raw": match.group(0),
                    "span": match.span(),
                    "left": left,
                    "right": right,
                }

        if best:
            f1, i1_text, _ = best["left"]
            f2, i2_text, _ = best["right"]
            i1_fmt = i1_text.replace(" ", "")
            i2_fmt = i2_text.replace(" ", "")
            dim_str = f"{f1}'-{i1_fmt}\"x{f2}'-{i2_fmt}\""
            start, end = best["span"]
            remaining = normalized[:start] + " " + normalized[end:]
            return dim_str, remaining.strip()

        # Token-order fallback for fragmented OCR like "<side1> <side2> X".
        tokens = normalized.split()
        for xi, token in enumerate(tokens):
            if token.lower() != "x":
                continue

            # Case A: "<side1> x <side2>"
            if xi - 1 >= 0 and xi + 1 < len(tokens):
                left = self._parse_dimension_side(tokens[xi - 1])
                right = self._parse_dimension_side(tokens[xi + 1])
                if left and right:
                    f1, i1_text, _ = left
                    f2, i2_text, _ = right
                    i1_fmt = i1_text.replace(" ", "")
                    i2_fmt = i2_text.replace(" ", "")
                    dim_str = f"{f1}'-{i1_fmt}\"x{f2}'-{i2_fmt}\""
                    remaining = " ".join(t for idx, t in enumerate(tokens) if idx not in {xi - 1, xi, xi + 1})
                    return dim_str, remaining.strip()

            # Case B: "<side1> <side2> x" (x appears at the end)
            if xi - 2 >= 0:
                left = self._parse_dimension_side(tokens[xi - 2])
                right = self._parse_dimension_side(tokens[xi - 1])
                if left and right:
                    f1, i1_text, _ = left
                    f2, i2_text, _ = right
                    i1_fmt = i1_text.replace(" ", "")
                    i2_fmt = i2_text.replace(" ", "")
                    dim_str = f"{f1}'-{i1_fmt}\"x{f2}'-{i2_fmt}\""
                    remaining = " ".join(t for idx, t in enumerate(tokens) if idx not in {xi - 2, xi - 1, xi})
                    return dim_str, remaining.strip()

        # Fallback: handle fragmented order like "<side1> <side2> x".
        tail_x_pattern = re.compile(r"([0-9'\"./\-\]\}\s]{1,24})\s+([0-9'\"./\-\]\}\s]{1,24})\s*x")
        for match in tail_x_pattern.finditer(normalized):
            left = self._parse_dimension_side(match.group(1))
            right = self._parse_dimension_side(match.group(2))
            if left and right:
                f1, i1_text, _ = left
                f2, i2_text, _ = right
                i1_fmt = i1_text.replace(" ", "")
                i2_fmt = i2_text.replace(" ", "")
                dim_str = f"{f1}'-{i1_fmt}\"x{f2}'-{i2_fmt}\""
                start, end = match.span()
                remaining = normalized[:start] + " " + normalized[end:]
                return dim_str, remaining.strip()

        return None, normalized

    def _extract_dimension_from_tokens(
        self,
        tokens: List[str],
        max_feet: int = 60
    ) -> Optional[str]:
        """
        Fallback dimension extraction from fragmented tokens.

        Useful when OCR yields separate sides without a clean 'x', e.g.:
            ['Toilet', '4\'-0"', "7'-6"].
        """
        candidates = []

        for i, token in enumerate(tokens):
            parsed = self._parse_dimension_side(token)
            if parsed:
                feet, inches_text, score = parsed
                if 1 <= feet <= max_feet:
                    candidates.append((i, feet, inches_text, score))

            # Try merged neighbors to recover split side fragments.
            if i + 1 < len(tokens):
                merged = f"{token} {tokens[i + 1]}"
                parsed_merged = self._parse_dimension_side(merged)
                if parsed_merged:
                    feet, inches_text, score = parsed_merged
                    if 1 <= feet <= max_feet:
                        candidates.append((i, feet, inches_text, score + 1))

        if len(candidates) < 2:
            return None

        # Prefer high-confidence nearby pairs in reading order.
        best = None
        for a in range(len(candidates)):
            for b in range(a + 1, len(candidates)):
                i1, f1, in1, s1 = candidates[a]
                i2, f2, in2, s2 = candidates[b]
                if i1 == i2:
                    continue
                if f1 == f2 and in1 == in2 and abs(i2 - i1) <= 2:
                    continue
                score = s1 + s2 - min(abs(i2 - i1), 5) * 0.2
                if best is None or score > best[0]:
                    best = (score, i1, f1, in1, i2, f2, in2)

        if not best:
            return None

        _, i1, f1, in1, i2, f2, in2 = best
        # Preserve text order.
        if i2 < i1:
            f1, in1, f2, in2 = f2, in2, f1, in1

        in1_fmt = in1.replace(" ", "")
        in2_fmt = in2.replace(" ", "")
        return f"{f1}'-{in1_fmt}\"x{f2}'-{in2_fmt}\""

    def _inches_text_to_float(self, inches_text: str) -> float:
        """Convert inches text like '7', '7-1/2' or '7 3/4' to float inches."""
        txt_raw = inches_text.strip()
        if not txt_raw:
            return 0.0
        txt = txt_raw.replace(" ", "")

        # Explicit fraction parsing.
        frac_match = re.search(r"(\d+)?[-\s]?(\d)\s*/\s*(\d{1,2})", txt_raw)
        if frac_match:
            base_txt = frac_match.group(1) or "0"
            num = int(frac_match.group(2))
            den = int(frac_match.group(3))
            if den in {2, 4, 8, 16} and 0 <= num < den:
                base = float(base_txt) if base_txt.isdigit() else 0.0
                return base + (num / den)

        # OCR legacy half-inch shorthand.
        if "-1/2" in txt or "1/2" in txt_raw:
            base = re.sub(r"[-\s]*1/2", "", txt_raw).strip()
            base_val = float(base) if base.isdigit() else 0.0
            return base_val + 0.5

        if txt.isdigit():
            return float(txt)
        return 0.0

    def _parse_dimension_numeric(self, dimension_text: str) -> Optional[Tuple[float, float]]:
        """Parse normalized dimension string into (side1_ft, side2_ft)."""
        normalized = self._normalize_ocr_text(dimension_text)
        match = re.search(
            r"(\d{1,2})\s*'\s*-\s*([\d]+(?:[-\s]\d/\d{1,2})?)\s*\"\s*x\s*(\d{1,2})\s*'\s*-\s*([\d]+(?:[-\s]\d/\d{1,2})?)\s*\"",
            normalized,
            re.IGNORECASE,
        )
        if not match:
            return None

        f1 = int(match.group(1))
        i1 = self._inches_text_to_float(match.group(2))
        f2 = int(match.group(3))
        i2 = self._inches_text_to_float(match.group(4))
        side1 = f1 + (i1 / 12.0)
        side2 = f2 + (i2 / 12.0)
        return side1, side2

    def _normalize_inches_display(self, inches_text: str) -> str:
        """Format inches token into canonical text (e.g., 7-1/2 -> 7 1/2)."""
        txt = inches_text.strip().replace(" ", "")
        frac_match = re.search(r"^(\d+)-(\d/\d{1,2})$", txt)
        if frac_match:
            return f"{frac_match.group(1)} {frac_match.group(2)}"
        if "-1/2" in txt:
            return txt.replace("-1/2", " 1/2")
        return txt

    def _canonicalize_dimension_text(self, dimension_text: str) -> str:
        """
        Convert parsed dimensions to a stable display format:
            12'-0"x10'-7 1/2"
        """
        normalized = self._normalize_ocr_text(dimension_text)
        match = re.search(
            r"(\d{1,2})\s*'\s*-\s*([\d]+(?:[-\s]\d/\d{1,2})?)\s*\"\s*x\s*(\d{1,2})\s*'\s*-\s*([\d]+(?:[-\s]\d/\d{1,2})?)\s*\"",
            normalized,
            re.IGNORECASE,
        )
        if not match:
            # At least force a consistent lowercase separator.
            return re.sub(r"\s*[xX]\s*", "x", normalized).strip()

        f1, i1, f2, i2 = match.group(1), match.group(2), match.group(3), match.group(4)
        i1_fmt = self._normalize_inches_display(i1)
        i2_fmt = self._normalize_inches_display(i2)
        return f"{f1}'-{i1_fmt}\"x{f2}'-{i2_fmt}\""

    def _dimension_quality_score(self, class_name: str, dimension_text: str) -> Tuple[bool, float]:
        """
        Validate parsed dimensions against class-aware size ranges.
        Returns (is_valid, confidence_0_to_1).
        """
        sides = self._parse_dimension_numeric(dimension_text)
        if not sides:
            return False, 0.0

        cls_key = class_name.lower()
        min_ft, max_ft = self.class_dimension_ranges.get(cls_key, (2.0, 45.0))
        s1, s2 = sorted(sides)

        in_range = (min_ft <= s1 <= max_ft) and (min_ft <= s2 <= max_ft)
        if not in_range:
            return False, 0.0

        # Normalize confidence by distance from allowed bounds.
        span = max(max_ft - min_ft, 1e-6)
        m1 = min(s1 - min_ft, max_ft - s1) / span
        m2 = min(s2 - min_ft, max_ft - s2) / span
        confidence = max(0.35, min(0.99, 0.55 + 0.9 * min(m1, m2)))
        return True, round(confidence, 3)

    def _merge_text_regions(self, primary: List[TextRegion], secondary: List[TextRegion]) -> List[TextRegion]:
        """
        Merge OCR outputs from two scales and keep the stronger duplicate.
        """
        merged: Dict[Tuple[int, int, str], TextRegion] = {}
        for tr in primary + secondary:
            key = (
                int(round(tr.center[0] / 6.0)),
                int(round(tr.center[1] / 6.0)),
                self._normalize_ocr_text(tr.text).lower(),
            )
            prev = merged.get(key)
            if prev is None or tr.confidence > prev.confidence:
                merged[key] = tr
        return list(merged.values())

    def _extract_area_from_blob(self, text_blob: str) -> Tuple[Optional[str], str]:
        """
        Extract area string from merged text blob.
        
        Returns:
            Tuple of (area_string, remaining_text)
        """
        match = self.area_pattern.search(text_blob)
        if match:
            area_str = match.group(0).strip()
            remaining = text_blob[:match.start()] + " " + text_blob[match.end():]
            return area_str, remaining.strip()
        return None, text_blob
    
    def _clean_label(self, text_blob: str) -> Optional[str]:
        """
        Clean the remaining text to extract a valid room label.
        
        Removes:
            - Standalone numbers and dimension fragments
            - Door/window codes (D1, W1, etc.)
            - Navigation codes (UP, DN, etc.)
        
        Keeps:
            - Room name keywords
            - Multi-character words that look like labels
        """
        if not text_blob:
            return None
        
        words = text_blob.split()
        valid_words = []
        
        for word in words:
            # Clean the word of special chars for checking
            clean_word = re.sub(r"[^\w\s]", "", word).strip()
            
            if not clean_word:
                continue
            
            # Skip if matches ignore pattern
            if self.ignore_pattern.match(clean_word):
                continue
            
            # Skip pure numbers
            if clean_word.isdigit():
                continue

            # Skip noisy OCR fragments that contain digits (e.g., "7.It", "v1/")
            if any(ch.isdigit() for ch in clean_word):
                continue
            
            # Skip single characters (except common abbreviations)
            if len(clean_word) < 2:
                continue
            
            # Skip dimension-like fragments (e.g., "10'", "12\"", "0\"")
            if re.match(r"^\d+['\"\'\"\`\Â´]*$", word):
                continue
            
            # Keep the word
            valid_words.append(word)
        
        if not valid_words:
            return None
        
        # Join and clean up
        label = " ".join(valid_words)
        # Remove extra punctuation at start/end
        label = re.sub(r"^[\s\-\.\,]+|[\s\-\.\,]+$", "", label)
        if not label:
            return None

        # Token-level typo correction.
        tokens = label.split()
        corrected = []
        for t in tokens:
            stripped = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", t)
            if not stripped:
                continue
            key = stripped.lower()
            corrected.append(self.label_word_map.get(key, stripped))

        # Collapse immediate duplicates.
        deduped = []
        for t in corrected:
            if not deduped or deduped[-1].lower() != t.lower():
                deduped.append(t)

        # Collapse repeated full phrase halves: "Bed Room Bed Room" -> "Bed Room".
        n = len(deduped)
        if n % 2 == 0 and n > 1:
            half = n // 2
            if [w.lower() for w in deduped[:half]] == [w.lower() for w in deduped[half:]]:
                deduped = deduped[:half]

        cleaned = " ".join(deduped).strip()
        return cleaned if cleaned else None
    
    def map_text_to_rooms(
        self,
        rooms: List[DetectedRoom],
        text_regions: List[TextRegion]
    ) -> List[DetectedRoom]:
        """
        Map text to rooms using a robust 'Collect -> Sort -> Merge -> Parse' strategy.
        
        This approach handles OCR fragmentation by:
            1. COLLECT: Find all text regions whose center is inside each room polygon
            2. SORT: Order by Y-coordinate (top-to-bottom reading order)
            3. MERGE: Combine all text into a single string
            4. PARSE: Extract dimensions and area using regex patterns
            5. CLEAN: Filter noise to isolate the room name/label
        
        Args:
            rooms: List of detected rooms with Shapely polygons
            text_regions: List of extracted text regions
        
        Returns:
            Updated rooms with mapped labels, dimensions, and areas
        """
        print(f"[INFO] Mapping {len(text_regions)} text(s) to {len(rooms)} room(s)")

        # Pre-assign text to rooms using strict point-in-polygon first.
        room_to_texts: Dict[int, List[TextRegion]] = {i: [] for i in range(len(rooms))}
        orphan_dimensions: List[TextRegion] = []
        assisted_room_indices: Set[int] = set()

        for text_region in text_regions:
            point = Point(text_region.center)
            assigned_indices = []
            for idx, room in enumerate(rooms):
                if room.polygon.contains(point) or room.polygon.touches(point):
                    room_to_texts[idx].append(text_region)
                    assigned_indices.append(idx)

            norm_text = self._normalize_ocr_text(text_region.text).lower()
            is_full_dimension = (
                text_region.text_type == "dimension"
                and " x " in f" {norm_text} "
            )
            if not assigned_indices and is_full_dimension:
                orphan_dimensions.append(text_region)

        # Recover dimensions that land just outside polygon boundaries by
        # assigning them to the nearest room within a small distance threshold.
        for text_region in orphan_dimensions:
            point = Point(text_region.center)
            distances = [(idx, room.polygon.distance(point)) for idx, room in enumerate(rooms)]
            nearest_idx, nearest_dist = min(distances, key=lambda x: x[1])
            if nearest_dist <= 80:
                room_to_texts[nearest_idx].append(text_region)
                assisted_room_indices.add(nearest_idx)
                print(
                    f"  [Map Assist] Assigned orphan dimension '{text_region.text}' "
                    f"to Room {nearest_idx+1} (distance={nearest_dist:.1f})"
                )

        for room_idx, room in enumerate(rooms):
            # =====================================================================
            # 1. COLLECT: Find all text regions inside this room's polygon
            # =====================================================================
            contained_texts: List[TextRegion] = list(room_to_texts[room_idx])
            
            if not contained_texts:
                # No text found inside room, use YOLO class as fallback label
                room.label = room.class_name.replace("_", " ").title()
                room.dimension_source = None
                room.dimension_confidence = 0.0
                print(f"  [Room {room_idx+1}] No text found, using class: '{room.label}'")
                continue
            
            # =====================================================================
            # 2. SORT: Sort text regions top-to-bottom by Y-coordinate (reading order)
            # =====================================================================
            contained_texts.sort(key=lambda t: (t.center[1], t.center[0]))
            
            # Debug: Show collected text tokens
            tokens = [t.text for t in contained_texts]
            print(f"  [Room {room_idx+1}] Collected {len(tokens)} token(s): {tokens}")
            
            # =====================================================================
            # 3. MERGE: Combine all tokens into a single text blob
            # =====================================================================
            full_text_blob = " ".join([t.text for t in contained_texts])
            print(f"  [Room {room_idx+1}] Merged blob: '{full_text_blob}'")
            
            # =====================================================================
            # 4. PARSE: Extract structured data from the merged blob
            # =====================================================================
            
            # 4a. Extract DIMENSIONS first (they have the most specific patterns)
            dimension_source = None
            token_texts = [t.text for t in contained_texts]
            primary_dim, remaining_text = self._extract_dimension_from_blob(full_text_blob)
            best_dim = None
            best_source = None
            best_conf = 0.0

            if primary_dim:
                primary_dim = self._canonicalize_dimension_text(primary_dim)
                primary_valid, primary_conf = self._dimension_quality_score(room.class_name, primary_dim)
                if primary_valid:
                    best_dim = primary_dim
                    best_source = "direct"
                    best_conf = primary_conf

            # For class-sensitive small rooms or low-confidence parses, try token fallback.
            class_key = room.class_name.lower()
            class_max = int(self.class_dimension_ranges.get(class_key, (2.0, 45.0))[1])
            fallback_classes = {"toilet", "pooja_room", "pooja", "services", "wash", "utility"}
            should_try_fallback = (
                class_key in fallback_classes
                and (best_dim is None or best_conf < self.low_conf_dimension_threshold)
            )
            if should_try_fallback:
                token_dim = self._extract_dimension_from_tokens(token_texts, max_feet=max(10, class_max + 2))
                if token_dim:
                    token_dim = self._canonicalize_dimension_text(token_dim)
                    token_valid, token_conf = self._dimension_quality_score(room.class_name, token_dim)
                    if token_valid and (best_dim is None or token_conf > best_conf + 0.08):
                        best_dim = token_dim
                        best_source = "fragment_fallback"
                        best_conf = token_conf

            if best_dim:
                if room_idx in assisted_room_indices and best_source == "direct":
                    best_source = "nearest_room"
                room.dimensions = best_dim
                room.dimension_source = best_source
                room.dimension_confidence = best_conf
                print(
                    f"  [Room {room_idx+1}] Extracted dimension: '{best_dim}' "
                    f"(source={best_source}, conf={best_conf:.2f})"
                )
                dimension_source = best_source
            else:
                room.dimensions = None
                room.dimension_source = None
                room.dimension_confidence = 0.0
                if primary_dim:
                    print(
                        f"  [Room {room_idx+1}] Rejected dimension by class-range check: '{primary_dim}'"
                    )
            
            # 4b. Extract AREA from remaining text
            area, remaining_text = self._extract_area_from_blob(remaining_text)
            if area:
                room.area_text = area
                print(f"  [Room {room_idx+1}] Extracted area: '{area}'")
            
            # =====================================================================
            # 5. CLEAN: Extract room label from remaining text
            # =====================================================================
            label = self._clean_label(remaining_text)
            
            if label:
                room.label = label
                print(f"  [Room {room_idx+1}] Extracted label: '{label}'")
            else:
                # Fallback to YOLO class name if no valid label extracted
                room.label = room.class_name.replace("_", " ").title()
                print(f"  [Room {room_idx+1}] No label found, using class: '{room.label}'")
        
        # Summary statistics
        labeled_count = sum(1 for r in rooms if r.label)
        dim_count = sum(1 for r in rooms if r.dimensions)
        area_count = sum(1 for r in rooms if r.area_text)
        
        print(f"\n[INFO] Mapping Results:")
        print(f"  - Rooms with labels: {labeled_count}/{len(rooms)}")
        print(f"  - Rooms with dimensions: {dim_count}/{len(rooms)}")
        print(f"  - Rooms with area text: {area_count}/{len(rooms)}")
        
        return rooms
    
    # =========================================================================
    # FULL PIPELINE: Analyze
    # =========================================================================

    def analyze_pdf(
        self,
        pdf_path: Union[str, Path],
        conf_yolo: float = 0.4,
        conf_ocr: float = 0.3,
        ocr_preprocess: bool = True,
        ocr_scale: float = 2.0,
        ocr_multi_scale: bool = True,
        ocr_alt_scale: float = 3.0,
        visualize: bool = True,
        output_path: Optional[Union[str, Path]] = None,
        pdf_dpi: int = 300,  # Legacy param, now dpi_yolo
        pdf_pages: Optional[List[int]] = None,
        pdf_max_pages: int = 0,  # 0 = all pages
        pdf_use_text_layer: bool = True,
        pdf_text_min_words: int = 20,
        return_pages: bool = False,
        visualize_debug_tokens: bool = False,
        show_dimensions: bool = True,
        use_per_room_ocr: bool = True,
        per_room_ocr_scale: float = 4.0,
        filter_watermarks: bool = True,
        # NEW: Dual-DPI and Roboflow options
        dpi_yolo: int = 300,
        dpi_ocr: int = 600,
        use_roboflow_ocr: bool = True,
        roboflow_crop_upscale: float = 2.0,
        debug_save_room_crops: bool = False,
    ) -> Dict:
        """
        Analyze PDF input with dual-DPI rendering and Roboflow DocTR OCR.
        
        Args:
            pdf_path: Path to PDF file
            conf_yolo: YOLO confidence threshold
            conf_ocr: OCR confidence threshold
            ocr_preprocess: Apply OCR preprocessing (EasyOCR fallback)
            ocr_scale: OCR upscale factor (EasyOCR fallback)
            ocr_multi_scale: Run OCR at multiple scales (EasyOCR fallback)
            ocr_alt_scale: Alternative OCR scale (EasyOCR fallback)
            visualize: Create visualization
            output_path: Path for output files
            pdf_dpi: Legacy param (use dpi_yolo instead)
            pdf_pages: Specific pages to process (1-indexed)
            pdf_max_pages: Max pages to process (0 = all)
            pdf_use_text_layer: Try PDF text layer first
            pdf_text_min_words: Min words to use text layer
            return_pages: Return per-page results
            visualize_debug_tokens: Draw OCR token boxes
            show_dimensions: Show dimensions on visualization
            use_per_room_ocr: Use per-room OCR strategy
            per_room_ocr_scale: Scale for per-room EasyOCR
            filter_watermarks: Filter watermark text
            dpi_yolo: DPI for YOLO detection (300 recommended)
            dpi_ocr: DPI for OCR (600 for sharper text)
            use_roboflow_ocr: Use Roboflow DocTR OCR (else EasyOCR)
            roboflow_crop_upscale: Upscale factor for Roboflow crops
            debug_save_room_crops: Save room crop images for debugging
        """
        pdf_path = Path(pdf_path)
        print(f"\n{'='*60}")
        print(f"ANALYZING PDF: {pdf_path.name}")
        print(f"{'='*60}")
        
        # Use pdf_dpi as fallback for dpi_yolo
        if dpi_yolo == 300 and pdf_dpi != 300:
            dpi_yolo = pdf_dpi

        doc = self._open_pdf(pdf_path)
        page_count = doc.page_count
        
        # Debug directory for room crops
        debug_dir = None
        if debug_save_room_crops and output_path:
            debug_dir = Path(output_path).parent / "debug_crops"
        
        try:
            # Determine which pages to process
            if pdf_pages:
                page_indices: List[int] = []
                for p in pdf_pages:
                    pi = int(p)
                    # Accept 1-indexed pages from user configs
                    if pi >= 1:
                        pi -= 1
                    if 0 <= pi < page_count:
                        page_indices.append(pi)
            else:
                # pdf_max_pages <= 0 means "all pages"
                if pdf_max_pages is None or pdf_max_pages <= 0:
                    max_pages = page_count
                else:
                    max_pages = min(page_count, int(pdf_max_pages))
                page_indices = list(range(max_pages))

            if not page_indices:
                raise ValueError("No valid PDF pages selected for analysis.")
            
            print(f"[INFO] Processing {len(page_indices)} page(s) of {page_count}")
            print(f"[INFO] DPI: YOLO={dpi_yolo}, OCR={dpi_ocr}")

            page_results: List[Dict] = []
            for page_index in page_indices:
                print(f"\n[PDF PAGE] {page_index + 1}/{page_count}")
                
                # DUAL-DPI RENDER: Render at two DPIs
                page_img_yolo, page, ctx_yolo = self._render_pdf_page(
                    pdf_path, page_index, dpi=dpi_yolo, doc=doc
                )
                
                # Calculate scale factor between YOLO and OCR images
                scale_yolo_to_ocr = dpi_ocr / dpi_yolo

                print("[STEP 1] Detecting rooms with YOLO...")
                rooms = self.detect_rooms(page_img_yolo, conf_threshold=conf_yolo)

                text_regions: List[TextRegion] = []
                text_layer_used = False
                text_extraction_strategy = "none"
                
                # Strategy 1: Try PDF text layer
                if pdf_use_text_layer:
                    has_text_layer = self._pdf_page_has_text_layer(page, min_words=pdf_text_min_words)
                    if has_text_layer:
                        text_regions = self.extract_text_from_pdf_page(page, ctx_yolo, conf_threshold=0.0)
                        if len(text_regions) >= int(pdf_text_min_words):
                            text_layer_used = True
                            text_extraction_strategy = "pdf_text_layer"
                            print(f"[STEP 2] Using PDF text layer: {len(text_regions)} tokens")
                            # Map text to rooms using point-in-polygon
                            print("[STEP 3] Mapping text to rooms...")
                            rooms = self.map_text_to_rooms(rooms, text_regions)
                
                # Strategy 2: DUAL-PATH OCR (labels from global, dimensions from per-room)
                # This is the recommended strategy for crystal-clear PDF renders
                if not text_layer_used and use_per_room_ocr and rooms:
                    print(f"[STEP 2] Using DUAL-PATH OCR strategy...")
                    print(f"  - Labels: Global OCR (no restrictions)")
                    print(f"  - Dimensions: Per-room OCR (allowlist + 2-pass)")
                    
                    # Render high-DPI image for OCR
                    page_img_ocr, _, ctx_ocr = self._render_pdf_page(
                        pdf_path, page_index, dpi=dpi_ocr, doc=doc
                    )
                    
                    # Debug directory for this page
                    page_debug_dir = None
                    if debug_dir:
                        page_debug_dir = debug_dir / f"page_{page_index + 1}"
                    
                    # PATH A: Extract labels using global OCR (optimized for words)
                    print("[STEP 2a] Extracting labels (global OCR)...")
                    room_labels = self.extract_labels_global(
                        page_img_yolo,  # Use YOLO DPI image for labels
                        rooms,
                        conf_threshold=conf_ocr,
                        filter_watermarks=filter_watermarks,
                    )
                    
                    # PATH B: Extract dimensions using per-room specialized OCR
                    print("[STEP 2b] Extracting dimensions (per-room specialized OCR)...")
                    room_dimensions = self.extract_dimensions_per_room(
                        page_img_ocr,
                        rooms,
                        scale_yolo_to_ocr=scale_yolo_to_ocr,
                        debug_save=debug_save_room_crops,
                        debug_dir=page_debug_dir,
                    )
                    
                    # Combine results into rooms
                    print("[STEP 3] Combining label + dimension results...")
                    for room_idx, room in enumerate(rooms):
                        # Apply label
                        if room_idx in room_labels:
                            room.label = room_labels[room_idx]
                        else:
                            room.label = room.class_name.replace("_", " ").title()
                        
                        # Apply dimensions
                        if room_idx in room_dimensions and room_dimensions[room_idx]:
                            dim_blob = room_dimensions[room_idx]
                            # Parse the dimension blob
                            dim_result, _ = self._extract_dimension_from_blob(dim_blob)
                            if dim_result:
                                dim_result = self._canonicalize_dimension_text(dim_result)
                                valid, conf = self._dimension_quality_score(room.class_name, dim_result)
                                if valid:
                                    room.dimensions = dim_result
                                    room.dimension_source = "dual_path_ocr"
                                    room.dimension_confidence = conf
                    
                    text_extraction_strategy = "dual_path_ocr"
                    
                    # Count results
                    labels_found = sum(1 for r in rooms if r.label)
                    dims_found = sum(1 for r in rooms if r.dimensions)
                    print(f"[STEP 2] Dual-path OCR complete: {labels_found} labels, {dims_found} dimensions")
                
                # Strategy 3: EasyOCR fallback (per-room or global)
                if not text_layer_used and text_extraction_strategy == "none":
                    if use_per_room_ocr and rooms:
                        print("[STEP 2] Using EasyOCR per-room (fallback)...")
                        text_regions = self.extract_text_per_room(
                            page_img_yolo,
                            rooms,
                            conf_threshold=conf_ocr,
                            ocr_preprocess=ocr_preprocess,
                            base_scale=per_room_ocr_scale,
                            room_pad=self.room_crop_pad,
                            mask_to_polygon=True,
                            filter_watermarks=filter_watermarks,
                        )
                        text_extraction_strategy = "easyocr_per_room"
                    else:
                        print("[STEP 2] Using EasyOCR global (fallback)...")
                        text_regions = self.extract_text(
                            page_img_yolo,
                            conf_threshold=conf_ocr,
                            use_preprocessing=ocr_preprocess,
                            ocr_scale_factor=ocr_scale,
                        )
                        if ocr_preprocess and ocr_multi_scale and abs(ocr_alt_scale - ocr_scale) > 1e-6:
                            extra_regions = self.extract_text(
                                page_img_yolo,
                                conf_threshold=conf_ocr,
                                use_preprocessing=ocr_preprocess,
                                ocr_scale_factor=ocr_alt_scale,
                            )
                            text_regions = self._merge_text_regions(text_regions, extra_regions)
                        text_extraction_strategy = "easyocr_global"
                    
                    print(f"[STEP 2] OCR tokens: {len(text_regions)}")
                    print("[STEP 3] Mapping text to rooms...")
                    rooms = self.map_text_to_rooms(rooms, text_regions)

                rooms_data = self._rooms_to_dict(rooms)

                vis_image = None
                page_vis_path: Optional[Path] = None
                if visualize:
                    if output_path:
                        out = Path(output_path)
                        suffix = out.suffix if out.suffix else ".png"
                        page_vis_path = out.with_name(f"{out.stem}_p{page_index + 1}{suffix}")
                    print("[STEP 4] Creating visualization...")
                    vis_image = self._visualize(
                        page_img_yolo,
                        rooms,
                        text_regions,
                        page_vis_path,
                        visualize_debug_tokens=visualize_debug_tokens,
                        show_dimensions=show_dimensions,
                    )

                if visualize_debug_tokens and output_path:
                    out = Path(output_path)
                    suffix = out.suffix if out.suffix else ".png"
                    debug_path = out.with_name(f"{out.stem}_p{page_index + 1}_tokens{suffix}")
                    self.debug_draw_pdf_word_boxes(page_img_yolo, text_regions, debug_path, n=50)

                summary = {
                    "page_index": page_index + 1,
                    "text_layer_used": text_layer_used,
                    "text_extraction_strategy": text_extraction_strategy,
                    "total_words_extracted": len(text_regions),
                    "total_rooms": len(rooms),
                    "rooms_with_labels": sum(1 for r in rooms if r.label),
                    "rooms_with_dimensions": sum(1 for r in rooms if r.dimensions),
                    "dpi_yolo": dpi_yolo,
                    "dpi_ocr": dpi_ocr,
                }
                
                # Print per-page summary
                print(f"\n[PAGE {page_index + 1} SUMMARY]")
                print(f"  Strategy: {text_extraction_strategy}")
                print(f"  Tokens: {len(text_regions)}")
                print(f"  Rooms: {len(rooms)}")
                print(f"  With dimensions: {summary['rooms_with_dimensions']}/{len(rooms)}")
                
                page_results.append(
                    {
                        "page_index": page_index + 1,
                        "rooms": rooms_data,
                        "summary": summary,
                        "visualization": vis_image,
                    }
                )
        finally:
            doc.close()

        if not return_pages and len(page_results) == 1:
            only = page_results[0]
            return {
                "rooms": only["rooms"],
                "visualization": only["visualization"],
                "summary": only["summary"],
            }

        return {
            "source": {
                "type": "pdf",
                "file": str(pdf_path),
                "dpi_yolo": dpi_yolo,
                "dpi_ocr": dpi_ocr,
                "page_count": int(page_count),
                "pages_processed": len(page_results),
            },
            "pages": page_results,
        }

    def analyze(
        self,
        image_path: Union[str, Path],
        conf_yolo: float = 0.4,
        conf_ocr: float = 0.3,
        ocr_preprocess: bool = True,
        ocr_scale: float = 2.0,
        ocr_multi_scale: bool = True,
        ocr_alt_scale: float = 3.0,
        visualize: bool = True,
        output_path: Optional[Union[str, Path]] = None,
        pdf_dpi: int = 300,
        pdf_pages: Optional[List[int]] = None,
        pdf_max_pages: int = 0,  # 0 = all pages
        pdf_use_text_layer: bool = True,
        pdf_text_min_words: int = 20,
        return_pages: bool = False,
        visualize_debug_tokens: bool = False,
        show_dimensions: bool = True,
        use_per_room_ocr: bool = True,
        per_room_ocr_scale: float = 4.0,
        filter_watermarks: bool = True,
        # NEW: Roboflow OCR options
        dpi_yolo: int = 300,
        dpi_ocr: int = 600,
        use_roboflow_ocr: bool = True,
        roboflow_crop_upscale: float = 2.0,
        debug_save_room_crops: bool = False,
    ) -> Dict:
        """
        Run complete analysis pipeline.
        
        Steps:
            1. Detect rooms (YOLO) - uses ORIGINAL image
            2. Extract text (EasyOCR, Roboflow, or PDF text layer)
            3. Map text to rooms (Point-in-Polygon)
            4. Visualize results (optional)
        
        Args:
            image_path: Path to floor plan image or PDF
            conf_yolo: YOLO confidence threshold
            conf_ocr: OCR confidence threshold
            ocr_preprocess: Enable OCR preprocessing
            ocr_scale: OCR upscale factor
            ocr_multi_scale: Run OCR at multiple scales
            ocr_alt_scale: Secondary OCR scale
            visualize: Create visualization
            output_path: Path to save visualization
            pdf_dpi: PDF rendering DPI (legacy, use dpi_yolo)
            pdf_pages: Specific PDF pages (1-indexed)
            pdf_max_pages: Max pages (0 = all)
            pdf_use_text_layer: Try PDF text layer first
            pdf_text_min_words: Min words to use text layer
            return_pages: Return per-page results for PDFs
            visualize_debug_tokens: Draw OCR token boxes
            show_dimensions: Show dimensions on visualization
            use_per_room_ocr: Per-room OCR for scanned PDFs
            per_room_ocr_scale: Scale for per-room EasyOCR
            filter_watermarks: Filter watermark text
            dpi_yolo: DPI for YOLO detection
            dpi_ocr: DPI for OCR (higher = sharper text)
            use_roboflow_ocr: Use Roboflow DocTR OCR
            roboflow_crop_upscale: Upscale for Roboflow crops
            debug_save_room_crops: Save debug crop images
        
        Returns:
            Dict with rooms, visualization, and summary
        """
        image_path = Path(image_path)
        if image_path.suffix.lower() == ".pdf":
            return self.analyze_pdf(
                pdf_path=image_path,
                conf_yolo=conf_yolo,
                conf_ocr=conf_ocr,
                ocr_preprocess=ocr_preprocess,
                ocr_scale=ocr_scale,
                ocr_multi_scale=ocr_multi_scale,
                ocr_alt_scale=ocr_alt_scale,
                visualize=visualize,
                output_path=output_path,
                pdf_dpi=pdf_dpi,
                pdf_pages=pdf_pages,
                pdf_max_pages=pdf_max_pages,
                pdf_use_text_layer=pdf_use_text_layer,
                pdf_text_min_words=pdf_text_min_words,
                return_pages=return_pages,
                visualize_debug_tokens=visualize_debug_tokens,
                show_dimensions=show_dimensions,
                use_per_room_ocr=use_per_room_ocr,
                per_room_ocr_scale=per_room_ocr_scale,
                filter_watermarks=filter_watermarks,
                dpi_yolo=dpi_yolo,
                dpi_ocr=dpi_ocr,
                use_roboflow_ocr=use_roboflow_ocr,
                roboflow_crop_upscale=roboflow_crop_upscale,
                debug_save_room_crops=debug_save_room_crops,
            )

        print(f"\n{'='*60}")
        print(f"ANALYZING: {image_path.name}")
        print(f"{'='*60}")
        
        # Load image ONCE
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Failed to read: {image_path}")
        
        # Keep independent clean copies so OCR preprocessing never affects YOLO input.
        yolo_image = image.copy()
        ocr_source_image = image.copy()

        # Step 1: Detect rooms (YOLO uses ORIGINAL image - no upscaling needed)
        print("\n[STEP 1] Detecting rooms with YOLO...")
        rooms = self.detect_rooms(yolo_image, conf_threshold=conf_yolo)
        
        # Step 2: Extract text (OCR uses PREPROCESSED image for better accuracy)
        print("\n[STEP 2] Extracting text with EasyOCR...")
        text_regions = self.extract_text(
            ocr_source_image,
            conf_threshold=conf_ocr,
            use_preprocessing=ocr_preprocess,
            ocr_scale_factor=ocr_scale
        )
        if ocr_preprocess and ocr_multi_scale and abs(ocr_alt_scale - ocr_scale) > 1e-6:
            extra_regions = self.extract_text(
                ocr_source_image,
                conf_threshold=conf_ocr,
                use_preprocessing=ocr_preprocess,
                ocr_scale_factor=ocr_alt_scale
            )
            merged_regions = self._merge_text_regions(text_regions, extra_regions)
            print(
                f"[INFO] Multi-scale OCR merge: base={len(text_regions)}, "
                f"alt={len(extra_regions)}, merged={len(merged_regions)}"
            )
            text_regions = merged_regions
        
        # Step 3: Map text to rooms
        print("\n[STEP 3] Mapping text to rooms...")
        rooms = self.map_text_to_rooms(rooms, text_regions)
        
        # Convert to output format
        rooms_data = self._rooms_to_dict(rooms)
        
        # Visualization
        vis_image = None
        if visualize:
            print("\n[STEP 4] Creating visualization...")
            vis_image = self._visualize(
                image,
                rooms,
                text_regions,
                output_path,
                visualize_debug_tokens=visualize_debug_tokens,
            )
        
        # Summary
        summary = {
            "total_rooms": len(rooms),
            "rooms_with_labels": sum(1 for r in rooms if r.label),
            "rooms_with_dimensions": sum(1 for r in rooms if r.dimensions),
            "total_text_regions": len(text_regions)
        }
        
        print(f"\n{'='*60}")
        print("ANALYSIS COMPLETE")
        print(f"{'='*60}")
        print(f"  Rooms detected: {summary['total_rooms']}")
        print(f"  Rooms with labels: {summary['rooms_with_labels']}")
        print(f"  Rooms with dimensions: {summary['rooms_with_dimensions']}")
        print(f"{'='*60}\n")
        
        return {
            "rooms": rooms_data,
            "visualization": vis_image,
            "summary": summary
        }
    
    def _rooms_to_dict(self, rooms: List[DetectedRoom]) -> List[Dict]:
        """Convert DetectedRoom objects to JSON-serializable dicts."""
        return [
            {
                "class_name": room.class_name,
                "label": room.label,
                "dimensions": room.dimensions,
                "dimension_source": room.dimension_source,
                "dimension_confidence": round(float(room.dimension_confidence), 3),
                "area_text": room.area_text,
                "confidence": round(room.confidence, 3),
                "area_pixels": round(room.area_pixels, 1),
                "centroid": {
                    "x": round(room.polygon.centroid.x, 1),
                    "y": round(room.polygon.centroid.y, 1)
                },
                "bbox": room.bbox
            }
            for room in rooms
        ]
    
    def _visualize(
        self,
        image: np.ndarray,
        rooms: List[DetectedRoom],
        text_regions: List[TextRegion],
        output_path: Optional[Path],
        visualize_debug_tokens: bool = False,
        show_dimensions: bool = False,
    ) -> np.ndarray:
        """
        Create visualization with room polygons and room names.
        
        Args:
            image: Source image
            rooms: Detected rooms
            text_regions: Text regions for debug overlay
            output_path: Path to save visualization
            visualize_debug_tokens: Draw OCR token boxes
            show_dimensions: Show dimensions below room labels
        """
        vis = image.copy()
        
        # Colors (BGR)
        CYAN = (255, 255, 0)
        GREEN = (0, 255, 0)
        YELLOW = (0, 255, 255)
        WHITE = (255, 255, 255)
        
        # Draw room polygons
        for room in rooms:
            coords = np.array(room.polygon.exterior.coords, dtype=np.int32)
            
            # Draw polygon outline (cyan)
            cv2.polylines(vis, [coords], True, CYAN, 2)
            
            # Prepare label text
            label = room.label if room.label else room.class_name
            dim_text = room.dimensions if show_dimensions and room.dimensions else None
            
            # Draw label at centroid
            if label:
                cx, cy = int(room.polygon.centroid.x), int(room.polygon.centroid.y)
                
                # Calculate text sizes
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                
                if dim_text:
                    (tw_dim, th_dim), _ = cv2.getTextSize(dim_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                    total_height = th + th_dim + 8
                    max_width = max(tw, tw_dim)
                    
                    # Background rectangle for both lines
                    cv2.rectangle(vis, (cx-4, cy-th-6), (cx+max_width+4, cy+th_dim+8), (0, 0, 0), -1)
                    
                    # Draw label (line 1)
                    cv2.putText(vis, label, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, CYAN, 2, cv2.LINE_AA)
                    
                    # Draw dimensions (line 2, smaller font)
                    cv2.putText(vis, dim_text, (cx, cy + th + 4), cv2.FONT_HERSHEY_SIMPLEX,
                               0.45, WHITE, 1, cv2.LINE_AA)
                else:
                    # Background rectangle for label only
                    cv2.rectangle(vis, (cx-4, cy-th-6), (cx+tw+4, cy+6), (0, 0, 0), -1)
                    
                    # Draw label
                    cv2.putText(vis, label, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, CYAN, 2, cv2.LINE_AA)
        
        # Draw text regions.
        if visualize_debug_tokens:
            if len(text_regions) > 30:
                chosen = np.random.choice(len(text_regions), size=30, replace=False)
                debug_regions = [text_regions[int(i)] for i in chosen]
            else:
                debug_regions = text_regions
            for tr in debug_regions:
                x1, y1, x2, y2 = tr.bbox
                color = GREEN if tr.text_type == "label" else YELLOW
                cv2.rectangle(vis, (x1, y1), (x2, y2), color, 1)
                cv2.putText(
                    vis,
                    tr.text[:24],
                    (x1, max(8, y1 - 2)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    color,
                    1,
                    cv2.LINE_AA,
                )
        else:
            for tr in text_regions:
                cx, cy = int(tr.center[0]), int(tr.center[1])
                color = GREEN if tr.text_type == "label" else YELLOW
                cv2.circle(vis, (cx, cy), 3, color, -1)
        
        # Save or return
        if output_path:
            cv2.imwrite(str(output_path), vis)
            print(f"[INFO] Saved visualization: {output_path}")
        
        return vis


# =============================================================================
# MAIN: Direct Usage
# =============================================================================
if __name__ == "__main__":
    import io
    import json
    import os
    import sys
    from collections import Counter
    from contextlib import redirect_stdout
    from pathlib import Path as _Path

    # -------------------------------------------------------------------------
    # EDITABLE CONFIG (no argparse required)
    # -------------------------------------------------------------------------
    CONFIG = {
        # mode: "single" or "batch"
        "mode": "single",
        "model_path": "/kaggle/input/datasets/parthtalsania/final-floor-yolo/runs/segment/runs/segment/floor_plan_rooms/weights/best.pt",
        "image_path": "/kaggle/input/datasets/parthtalsania/floor-dataset/Dataset/Dataset/AAHHP/E-01.png",
        "pdf_path": None,  # e.g. "/kaggle/input/.../Test_5.pdf"
        "pdf_pages": None,  # e.g. [1, 2, 3] (1-indexed) or None for all
        "pdf_max_pages": 0,  # 0 = all pages, >0 = limit
        "pdf_dpi": 300,  # Legacy, use dpi_yolo
        "pdf_use_text_layer": True,
        "pdf_text_min_words": 20,
        "return_pages": True,
        "visualize_debug_tokens": True,  # Draw OCR token boxes for debugging
        "show_dimensions": True,  # Show dimensions on visualization
        "use_per_room_ocr": True,  # Per-room OCR for scanned PDFs
        "per_room_ocr_scale": 4.0,  # Scale for per-room EasyOCR
        "filter_watermarks": True,  # Filter watermark text
        # NEW: Dual-DPI and Roboflow OCR options
        "dpi_yolo": 300,  # DPI for YOLO detection
        "dpi_ocr": 600,  # DPI for OCR (higher = sharper text)
        "use_roboflow_ocr": True,  # Use Roboflow DocTR OCR (else EasyOCR)
        "roboflow_crop_upscale": 2.0,  # Upscale factor for Roboflow crops
        "debug_save_room_crops": False,  # Save room crop images for debugging
        # Other settings
        "dataset_dir": "/kaggle/input/datasets/parthtalsania/floor-dataset/Dataset/Dataset/AAHHP",
        "output_dir": "/kaggle/working",
        "report_json": "batch_verification_report_v3.json",
        "use_gpu": True,
        "quiet_per_image": True,
        "visualize": True,
        "conf_yolo": 0.4,
        "conf_ocr": 0.3,
        "ocr_scale": 2.5,
        "ocr_multi_scale": True,
        "ocr_alt_scale": 3.0,
    }

    try:
        output_dir = CONFIG["output_dir"]
        os.makedirs(output_dir, exist_ok=True)
        analyzer = FloorPlanAnalyzer(model_path=CONFIG["model_path"], use_gpu=CONFIG["use_gpu"])

        if CONFIG["mode"] == "single":
            image_path = CONFIG.get("pdf_path") or CONFIG["image_path"]
            image_basename = os.path.basename(str(image_path))
            image_name, _ = os.path.splitext(image_basename)
            output_image_path = os.path.join(output_dir, f"{image_name}_result.png")
            output_json_path = os.path.join(output_dir, f"{image_name}_data.json")

            print(f"\n[CONFIG] Input Image:  {image_path}")
            print(f"[CONFIG] Output Image: {output_image_path}")
            print(f"[CONFIG] Output JSON:  {output_json_path}")

            results = analyzer.analyze(
                image_path=image_path,
                conf_yolo=CONFIG["conf_yolo"],
                conf_ocr=CONFIG["conf_ocr"],
                ocr_preprocess=True,
                ocr_scale=CONFIG["ocr_scale"],
                ocr_multi_scale=CONFIG["ocr_multi_scale"],
                ocr_alt_scale=CONFIG["ocr_alt_scale"],
                visualize=CONFIG["visualize"],
                output_path=output_image_path if CONFIG["visualize"] else None,
                pdf_dpi=CONFIG.get("pdf_dpi", 300),
                pdf_pages=CONFIG.get("pdf_pages"),
                pdf_max_pages=CONFIG.get("pdf_max_pages", 0),
                pdf_use_text_layer=CONFIG.get("pdf_use_text_layer", True),
                pdf_text_min_words=CONFIG.get("pdf_text_min_words", 20),
                return_pages=CONFIG.get("return_pages", True),
                visualize_debug_tokens=CONFIG.get("visualize_debug_tokens", False),
                show_dimensions=CONFIG.get("show_dimensions", True),
                use_per_room_ocr=CONFIG.get("use_per_room_ocr", True),
                per_room_ocr_scale=CONFIG.get("per_room_ocr_scale", 4.0),
                filter_watermarks=CONFIG.get("filter_watermarks", True),
                # NEW: Roboflow OCR options
                dpi_yolo=CONFIG.get("dpi_yolo", 300),
                dpi_ocr=CONFIG.get("dpi_ocr", 600),
                use_roboflow_ocr=CONFIG.get("use_roboflow_ocr", True),
                roboflow_crop_upscale=CONFIG.get("roboflow_crop_upscale", 2.0),
                debug_save_room_crops=CONFIG.get("debug_save_room_crops", False),
            )

            if "pages" in results:
                rooms_data = []
                for page_item in results.get("pages", []):
                    rooms_data.extend(page_item.get("rooms", []))
            else:
                rooms_data = results.get("rooms", [])
            print("\n" + "=" * 60)
            print("ROOM DETAILS")
            print("=" * 60)
            for i, room in enumerate(rooms_data, 1):
                print(f"\n[Room {i}]")
                print(f"  Label:      {room.get('label', 'N/A')}")
                print(f"  Dimensions: {room.get('dimensions', 'N/A')}")
                print(f"  Dim Source: {room.get('dimension_source', 'N/A')}")
                print(f"  Dim Conf:   {room.get('dimension_confidence', 0.0)}")
                print(f"  Area Text:  {room.get('area_text', 'N/A')}")
                print(f"  Class:      {room.get('class_name', 'N/A')}")
                print(f"  Confidence: {room.get('confidence', 0):.1%}")

            export_data = {
                "source_image": str(image_path),
                "total_rooms": len(rooms_data),
                "rooms": rooms_data,
                "summary": results.get("summary", {}),
                "pages": (
                    [
                        {
                            "page_index": p.get("page_index"),
                            "summary": p.get("summary", {}),
                            "rooms": p.get("rooms", []),
                        }
                        for p in results.get("pages", [])
                    ]
                    if isinstance(results, dict) and "pages" in results
                    else None
                ),
            }
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
            print(f"[SUCCESS] JSON exported to: {output_json_path}")
            if CONFIG["visualize"]:
                print(f"[SUCCESS] Image saved to:   {output_image_path}")
            print(f"[INFO] JSON file size: {os.path.getsize(output_json_path)} bytes")

        else:
            dataset_dir = _Path(CONFIG["dataset_dir"])
            if not dataset_dir.exists():
                raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
            exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
            images = sorted([p for p in dataset_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts])
            if not images:
                raise ValueError(f"No images found in dataset dir: {dataset_dir}")

            print(f"\n[CONFIG] Batch Dataset: {dataset_dir}")
            print(f"[CONFIG] Total Images:  {len(images)}")
            print(f"[CONFIG] Output Dir:    {output_dir}")

            report = {
                "total_images": len(images),
                "processed": 0,
                "failed": 0,
                "failures": [],
                "settings": {
                    "conf_yolo": CONFIG["conf_yolo"],
                    "conf_ocr": CONFIG["conf_ocr"],
                    "ocr_preprocess": True,
                    "ocr_scale": CONFIG["ocr_scale"],
                    "ocr_multi_scale": CONFIG["ocr_multi_scale"],
                    "ocr_alt_scale": CONFIG["ocr_alt_scale"],
                },
                "class_stats": {},
            }

            class_total = Counter()
            class_with_label = Counter()
            class_with_dim = Counter()
            source_counts = Counter()
            conf_sum = Counter()
            conf_n = Counter()

            for idx, img_path in enumerate(images, 1):
                try:
                    if CONFIG["quiet_per_image"]:
                        with redirect_stdout(io.StringIO()):
                            results = analyzer.analyze(
                                image_path=img_path,
                                conf_yolo=CONFIG["conf_yolo"],
                                conf_ocr=CONFIG["conf_ocr"],
                                ocr_preprocess=True,
                                ocr_scale=CONFIG["ocr_scale"],
                                ocr_multi_scale=CONFIG["ocr_multi_scale"],
                                ocr_alt_scale=CONFIG["ocr_alt_scale"],
                                visualize=False,
                            )
                    else:
                        results = analyzer.analyze(
                            image_path=img_path,
                            conf_yolo=CONFIG["conf_yolo"],
                            conf_ocr=CONFIG["conf_ocr"],
                            ocr_preprocess=True,
                            ocr_scale=CONFIG["ocr_scale"],
                            ocr_multi_scale=CONFIG["ocr_multi_scale"],
                            ocr_alt_scale=CONFIG["ocr_alt_scale"],
                            visualize=False,
                        )

                    report["processed"] += 1
                    for room in results.get("rooms", []):
                        cls = room.get("class_name") or "Unknown"
                        class_total[cls] += 1
                        if room.get("label"):
                            class_with_label[cls] += 1
                        if room.get("dimensions"):
                            class_with_dim[cls] += 1
                            src = room.get("dimension_source") or "unknown"
                            source_counts[src] += 1
                            conf = float(room.get("dimension_confidence") or 0.0)
                            conf_sum[cls] += conf
                            conf_n[cls] += 1
                except Exception as e:
                    report["failed"] += 1
                    report["failures"].append({"image": str(img_path), "error": f"{type(e).__name__}: {e}"})

                if idx % 10 == 0 or idx == len(images):
                    print(f"[PROGRESS] {idx}/{len(images)}")

            for cls in sorted(class_total):
                total = class_total[cls]
                with_label = class_with_label[cls]
                with_dim = class_with_dim[cls]
                avg_conf = (conf_sum[cls] / conf_n[cls]) if conf_n[cls] else 0.0
                report["class_stats"][cls] = {
                    "total_rooms": total,
                    "with_label": with_label,
                    "with_label_pct": round((with_label / total) * 100, 2) if total else 0.0,
                    "with_dimensions": with_dim,
                    "with_dimensions_pct": round((with_dim / total) * 100, 2) if total else 0.0,
                    "avg_dimension_confidence": round(avg_conf, 3),
                }

            total_rooms = sum(class_total.values())
            rooms_with_dims = sum(class_with_dim.values())
            report["global"] = {
                "total_rooms": total_rooms,
                "rooms_with_dimensions": rooms_with_dims,
                "rooms_with_dimensions_pct": round((rooms_with_dims / total_rooms) * 100, 2) if total_rooms else 0.0,
                "dimension_source_counts": dict(source_counts),
            }

            report_path = _Path(output_dir) / CONFIG["report_json"]
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            print("\n=== SUMMARY (V3) ===")
            print(f"total_images: {report['total_images']}")
            print(f"processed: {report['processed']}")
            print(f"failed: {report['failed']}")
            print(f"global: {report['global']}")
            for key in ["Hall", "Kitchen", "Bedroom", "Master_Bedroom", "Toilet", "Pooja_room", "Dining", "Sit_out"]:
                if key in report["class_stats"]:
                    s = report["class_stats"][key]
                    print(
                        f"{key}: dims {s['with_dimensions']}/{s['total_rooms']} "
                        f"({s['with_dimensions_pct']}%), avg_conf={s['avg_dimension_confidence']}"
                    )
            print(f"saved: {report_path}")

    except FileNotFoundError as e:
        print(f"\n[ERROR] File not found: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"\n[ERROR] JSON encoding failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n[DONE] Analysis complete!")
