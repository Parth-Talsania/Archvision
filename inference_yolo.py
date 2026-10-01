"""
YOLOv8 Room Detection Inference Script
=======================================
Purpose: Replace OpenCV-based segment_rooms() with YOLO instance segmentation.

This script:
    1. Loads a trained YOLOv8-Seg model (best.pt)
    2. Detects rooms and extracts polygon masks
    3. Converts masks to Shapely Polygon objects (for OCR pairing)
    4. Visualizes results with cyan polygon outlines

Prerequisites:
    pip install ultralytics shapely opencv-python numpy

Usage:
    from inference_yolo import detect_rooms_yolo
    
    rooms = detect_rooms_yolo(
        model_path="runs/segment/floor_plan_rooms/weights/best.pt",
        image_path="floor_plan.png"
    )
    
    # Each room contains: polygon, class_name, confidence, bbox
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from dataclasses import dataclass

from ultralytics import YOLO
from shapely.geometry import Polygon
from shapely.validation import make_valid


@dataclass
class DetectedRoom:
    """Data class representing a detected room."""
    polygon: Polygon          # Shapely Polygon for geometric operations
    class_name: str           # Room type (e.g., "Bedroom", "Kitchen")
    confidence: float         # Detection confidence (0-1)
    bbox: Tuple[int, int, int, int]  # Bounding box (x1, y1, x2, y2)
    mask_points: np.ndarray   # Original mask points from YOLO
    area_pixels: float        # Area in pixels


def detect_rooms_yolo(
    model_path: Union[str, Path],
    image_path: Union[str, Path],
    conf_threshold: float = 0.4,
    visualize: bool = True,
    output_path: Optional[Union[str, Path]] = None
) -> Tuple[List[DetectedRoom], Optional[np.ndarray]]:
    """
    Detect rooms in a floor plan image using trained YOLOv8-Seg model.
    
    This function replaces the old OpenCV-based segment_rooms() function.
    
    Args:
        model_path: Path to trained YOLOv8-Seg model (best.pt)
        image_path: Path to floor plan image
        conf_threshold: Minimum confidence threshold (default: 0.4)
        visualize: Whether to draw polygons on image (default: True)
        output_path: Optional path to save visualized image
    
    Returns:
        Tuple of:
            - List[DetectedRoom]: Detected rooms with Shapely polygons
            - np.ndarray or None: Visualized image (if visualize=True)
    
    Example:
        rooms, vis_image = detect_rooms_yolo(
            model_path="best.pt",
            image_path="floor_plan.png"
        )
        
        for room in rooms:
            print(f"{room.class_name}: {room.confidence:.2f}")
            print(f"  Area: {room.polygon.area} px²")
            print(f"  Centroid: {room.polygon.centroid}")
    """
    
    # =========================================================================
    # STEP 1: Load Model
    # =========================================================================
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    
    model = YOLO(str(model_path))
    print(f"[INFO] Loaded model: {model_path.name}")
    
    # =========================================================================
    # STEP 2: Load Image
    # =========================================================================
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Failed to read image: {image_path}")
    
    original_image = image.copy()
    print(f"[INFO] Image size: {image.shape[1]}x{image.shape[0]}")
    
    # =========================================================================
    # STEP 3: Run Prediction
    # =========================================================================
    results = model.predict(
        source=image,
        conf=conf_threshold,
        save=False,
        verbose=False
    )
    
    # Get the first result (single image)
    result = results[0]
    
    # Check if any detections
    if result.masks is None:
        print("[WARN] No rooms detected in image")
        return [], original_image if visualize else None
    
    # =========================================================================
    # STEP 4: Extract Polygons and Convert to Shapely
    # =========================================================================
    detected_rooms: List[DetectedRoom] = []
    
    # Get class names from model
    class_names = result.names  # Dict: {0: 'Bedroom', 1: 'Kitchen', ...}
    
    # Iterate through each detection
    num_detections = len(result.masks.xy)
    print(f"[INFO] Detected {num_detections} room(s)")
    
    for i in range(num_detections):
        # Get mask polygon points (already in image coordinates)
        # result.masks.xy[i] is a numpy array of shape (N, 2)
        mask_points = result.masks.xy[i]
        
        # Skip if not enough points for a polygon (need at least 3)
        if len(mask_points) < 3:
            print(f"[WARN] Skipping detection {i}: insufficient points ({len(mask_points)})")
            continue
        
        # Convert to Shapely Polygon
        try:
            polygon = Polygon(mask_points)
            
            # Fix invalid polygons (self-intersecting, etc.)
            if not polygon.is_valid:
                polygon = make_valid(polygon)
                # make_valid might return MultiPolygon, take the largest
                if polygon.geom_type == 'MultiPolygon':
                    polygon = max(polygon.geoms, key=lambda p: p.area)
                elif polygon.geom_type != 'Polygon':
                    print(f"[WARN] Skipping detection {i}: invalid geometry after fix")
                    continue
            
            # Skip tiny polygons (noise)
            if polygon.area < 100:  # Less than 100 pixels
                continue
                
        except Exception as e:
            print(f"[WARN] Failed to create polygon for detection {i}: {e}")
            continue
        
        # Get class and confidence
        class_id = int(result.boxes.cls[i])
        class_name = class_names[class_id]
        confidence = float(result.boxes.conf[i])
        
        # Get bounding box
        box = result.boxes.xyxy[i].cpu().numpy()
        bbox = tuple(map(int, box))
        
        # Create DetectedRoom object
        room = DetectedRoom(
            polygon=polygon,
            class_name=class_name,
            confidence=confidence,
            bbox=bbox,
            mask_points=mask_points,
            area_pixels=polygon.area
        )
        detected_rooms.append(room)
        
        print(f"  [{i+1}] {class_name}: {confidence:.2f} conf, {polygon.area:.0f} px² area")
    
    # =========================================================================
    # STEP 5: Visualization (Cyan Polygon Outlines Only)
    # =========================================================================
    vis_image = None
    
    if visualize:
        vis_image = original_image.copy()
        
        # Cyan color in BGR format
        CYAN = (255, 255, 0)  # BGR: Cyan
        THICKNESS = 2
        
        for room in detected_rooms:
            # Get polygon exterior coordinates
            coords = np.array(room.polygon.exterior.coords, dtype=np.int32)
            
            # Draw polygon outline (NOT filled, NOT bbox)
            cv2.polylines(
                vis_image, 
                [coords], 
                isClosed=True, 
                color=CYAN, 
                thickness=THICKNESS
            )
            
            # Add label at centroid
            centroid = room.polygon.centroid
            label = f"{room.class_name}"
            label_pos = (int(centroid.x), int(centroid.y))
            
            # Draw label background
            (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(
                vis_image,
                (label_pos[0] - 2, label_pos[1] - text_h - 4),
                (label_pos[0] + text_w + 2, label_pos[1] + 4),
                (0, 0, 0),
                -1
            )
            
            # Draw label text
            cv2.putText(
                vis_image,
                label,
                label_pos,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                CYAN,
                1,
                cv2.LINE_AA
            )
        
        # Save if output path provided
        if output_path:
            output_path = Path(output_path)
            cv2.imwrite(str(output_path), vis_image)
            print(f"[INFO] Visualization saved to: {output_path}")
    
    return detected_rooms, vis_image


def get_room_polygons(rooms: List[DetectedRoom]) -> List[Polygon]:
    """
    Extract just the Shapely Polygons from detected rooms.
    
    Useful for integration with existing OCR pairing logic.
    
    Args:
        rooms: List of DetectedRoom objects
    
    Returns:
        List of Shapely Polygon objects
    """
    return [room.polygon for room in rooms]


def get_rooms_as_dict(rooms: List[DetectedRoom]) -> List[Dict]:
    """
    Convert detected rooms to dictionary format for JSON export.
    
    Args:
        rooms: List of DetectedRoom objects
    
    Returns:
        List of dictionaries with room information
    """
    return [
        {
            "class_name": room.class_name,
            "confidence": round(room.confidence, 3),
            "bbox": room.bbox,
            "area_pixels": round(room.area_pixels, 1),
            "centroid": {
                "x": round(room.polygon.centroid.x, 1),
                "y": round(room.polygon.centroid.y, 1)
            },
            "polygon_points": room.mask_points.tolist()
        }
        for room in rooms
    ]


# =============================================================================
# MAIN: Direct Usage (Edit paths below)
# =============================================================================
if __name__ == "__main__":
    
    # =========================================================================
    # >>> EDIT THESE PATHS <<<
    # =========================================================================
    MODEL_PATH = "results\runs\segment\runs\segment\floor_plan_rooms\weights\best.pt"  # Path to your trained model
    IMAGE_PATH = "Dataset\AAHHP\E-03.png"  # Path to floor plan image
    CONF_THRESHOLD = 0.4  # Confidence threshold (0.0 - 1.0)
    OUTPUT_IMAGE = "LOGS\results\resultsresult.png"  # Set to None to display instead of save
    # =========================================================================
    
    # Run detection
    rooms, vis_image = detect_rooms_yolo(
        model_path=MODEL_PATH,
        image_path=IMAGE_PATH,
        conf_threshold=CONF_THRESHOLD,
        visualize=True,
        output_path=OUTPUT_IMAGE
    )
    
    # Print summary
    print("\n" + "="*50)
    print("DETECTION SUMMARY")
    print("="*50)
    for room in rooms:
        print(f"\n{room.class_name}:")
        print(f"  Confidence: {room.confidence:.2%}")
        print(f"  Area: {room.area_pixels:,.0f} px²")
        print(f"  Centroid: ({room.polygon.centroid.x:.1f}, {room.polygon.centroid.y:.1f})")
        print(f"  Bbox: {room.bbox}")
    
    # Show visualization (if not saved)
    if vis_image is not None and OUTPUT_IMAGE is None:
        cv2.imshow("YOLO Room Detection", vis_image)
        print("\nPress any key to close...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
