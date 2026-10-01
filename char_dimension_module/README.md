# Character-Level Dimension Module (Standalone)

This folder is fully separate from your current pipeline code.

## What it provides

- Character-level dimension detector + parser:
  - `char_dimension_module/dimension_char_reader.py`
- Synthetic YOLO dataset generator:
  - `char_dimension_module/tools/gen_synth_dim_chars.py`
- YOLO training entrypoint:
  - `char_dimension_module/train_dim_chars.py`
- Optional adapter to enrich existing room JSON:
  - `char_dimension_module/integration_adapter.py`
- Optional wrapper for existing `floor_plan_pipeline.py`:
  - `char_dimension_module/floor_plan_pipeline_char.py`

## Character classes (fixed order)

1. `0`
2. `1`
3. `2`
4. `3`
5. `4`
6. `5`
7. `6`
8. `7`
9. `8`
10. `9`
11. `apostrophe`
12. `quote`
13. `slash`
14. `dash`
15. `x`
16. `dot`
17. `times`
18. `half`
19. `quarter`
20. `three_quarter`

## 1) Generate synthetic dataset

```bash
python char_dimension_module/tools/gen_synth_dim_chars.py \
  --out char_dimension_module/datasets/dim_chars \
  --train 20000 --val 2000
```

Quick bootstrap:

```bash
python char_dimension_module/tools/gen_synth_dim_chars.py --train 5000 --val 500
```

## 2) Train YOLO character detector

```bash
python char_dimension_module/train_dim_chars.py \
  --data char_dimension_module/datasets/dim_chars/dim_chars.yaml \
  --model yolov8n.pt --imgsz 1024 --epochs 120 --batch 16 --device 0
```

Best weights are saved by Ultralytics under:
`char_dimension_module/runs/detect/dim_chars/weights/best.pt`

## 3) Inference for one room polygon

```python
from shapely.geometry import Polygon
import cv2
from char_dimension_module.dimension_char_reader import extract_room_dimensions

img = cv2.imread("plan.png")
poly = Polygon([(10,10),(300,10),(300,200),(10,200)])
res = extract_room_dimensions(
    image=img,
    room_polygon=poly,
    model_path="char_dimension_module/runs/detect/dim_chars/weights/best.pt",
    device="cuda",
    debug=True,
    debug_path="debug_room.png",
)
print(res.dimensions_text)
print(res.parsed)
```

## 4) Unit tests (parser)

```bash
pytest -q char_dimension_module/tests/test_dimension_parser.py
```

## Notes

- Per-room masked crops are used by default.
- Crops are upscaled 2x before detection.
- Optional tiled inference is supported for large crops.
- Canonical output format is:
  - `FEET'-INCHES FRACTION"`
  - Example: `12'-6 1/2" x 10'-0"`
