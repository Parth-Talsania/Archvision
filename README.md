# Hybrid AI Floor Plan Analysis Pipeline (v2)

This repository now contains a **modular v2 pipeline** that keeps your original flow intact and adds:
- Per-room OCR (crop + polygon mask + preprocessing)
- OCR-box intersection-ratio association (with center fallback)
- Geometric OCR line grouping + token glue rules
- Structured dimension parsing
- Safe visualization hygiene (OCR always on clean images)
- Richer JSON schema with optional OCR debug payloads
- Evaluation harness + augmentation/training helper scripts

## New Structure

```text
pipeline/
  config.py
  types.py
  geometry.py
  yolo_rooms.py
  ocr_engine.py
  ocr_merge.py
  parse_semantics.py
  output_schema.py
  visualize.py
  pipeline.py
scripts/
  run_pipeline.py
  evaluate_pipeline.py
  augment_dataset.py
  train_yolo_helper.py
tests/
  test_parse_semantics.py
  test_ocr_merge.py
  test_geometry.py
  test_smoke_output.py
```

## Run Pipeline (v2)

Single image:

```bash
python scripts/run_pipeline.py ^
  --model "results/runs/segment/runs/segment/floor_plan_rooms/weights/best.pt" ^
  --image "Dataset/AAHHP/E-01.png" ^
  --output-dir "results/v2"
```

Dataset folder:

```bash
python scripts/run_pipeline.py ^
  --model "results/runs/segment/runs/segment/floor_plan_rooms/weights/best.pt" ^
  --dataset-dir "Dataset/AAHHP" ^
  --output-dir "results/v2_batch" ^
  --save-debug --include-ocr-raw
```

Kaggle-ready paths:
- model: `/kaggle/input/datasets/parthtalsania/final-floor-yolo/runs/segment/runs/segment/floor_plan_rooms/weights/best.pt`
- dataset: `/kaggle/input/datasets/parthtalsania/floor-dataset/Dataset/Dataset/AAHHP`

## Important Flags

- `--ocr-mode per_room|full_image` (default `per_room`)
- `--save-debug`
- `--debug-dir`
- `--include-ocr-raw`
- `--device auto|cpu|cuda`
- `--conf-yolo`, `--conf-ocr`, `--ocr-scale`, `--room-crop-pad`

Backward-compatible flags retained:
- `--disable-ocr-multi-scale`
- `--ocr-alt-scale`

## Output JSON (v2)

Top-level:
- `image`: filename/path/width/height
- `model`: model path, engine, version, timestamp
- `total_rooms`
- `rooms[]`

Per room:
- `id`, `yolo_confidence`
- `label`, `label_confidence`
- `dimensions_text`, `dimension_parsed`
- `area_text`, `area_ft2`, `area_px2`
- `centroid`, `polygon_coordinates`
- optional `ocr_raw`, `ocr_lines`, `ocr_merged_text`

Area rule:
- `area_px2` always present
- `area_ft2` computed from parsed dimensions only (no px->ft fabrication)

## Evaluation Harness

```bash
python scripts/evaluate_pipeline.py ^
  --pred-dir "results/v2_batch" ^
  --expected-dir "results/golden_expected" ^
  --out-json "results/eval_report_v2.json"
```

Expected JSON can include partial constraints:
- `min_rooms`, `max_rooms`
- `expected_labels`
- `expected_dimensions_present`

## Augmentation Script

```bash
python scripts/augment_dataset.py ^
  --images-dir "data/images/train" ^
  --labels-dir "data/labels/train" ^
  --out-images-dir "data_aug/images/train" ^
  --out-labels-dir "data_aug/labels/train" ^
  --copies 2
```

Includes:
- rotation/perspective/affine
- blur/noise/contrast/grayscale
- watermark simulation
- broken-line simulation

Polygons are transformed with the image and re-exported in YOLO-seg normalized format.

## Training Helper

```bash
python scripts/train_yolo_helper.py ^
  --data "data.yaml" ^
  --model "yolov8s-seg.pt" ^
  --imgsz 1024 ^
  --epochs 150 ^
  --batch 8
```

## Tests

```bash
pytest -q tests
```

If `pytest` is unavailable in environment, install it first:

```bash
pip install pytest
```

## PDF Floorplan Extractor (New Step-1 Module)

Independent module: `pdf_extract/`

Run:

```bash
python -m pdf_extract.cli_extract_floorplans ^
  --pdf "Dataset/PDF/Test_2.pdf" ^
  --out_dir "results/pdf_extract_test2" ^
  --save_debug
```

Main outputs:
- `out_dir/floorplans/*.png`
- `out_dir/manifest.json`
- `out_dir/debug/page_scores.csv` (if `--save_debug`)

Key knobs:
- `--min_page_score`
- `--min_crop_score`
- `--min_region_area_ratio`
- `--max_regions_per_page`
- `--validator none|yolo`
- `--min_rooms`

## Merged Full Pipeline (PDF -> JSON)

Single command:

```bash
python -m full_pipeline.run ^
  --pdf "Dataset/PDF/Test_2.pdf" ^
  --out_dir "results/full_merged_test2" ^
  --yolo_model "results/runs/segment/runs/segment/floor_plan_rooms/weights/best.pt" ^
  --text-source auto --ocr-engine paddle --save-text-debug
```

Main artifact:
- `out_dir/final_output.json`

The merged pipeline keeps extractor and analyzer as standalone modules and integrates them through importable APIs.

### Why PDF Text Beats OCR

For digital PDFs with text layers, the pipeline now prefers PyMuPDF-native word extraction (`pdf_text`) over OCR.
This avoids rasterization loss and greatly improves room label/dimension recovery.
OCR is used only as fallback when PDF text in the crop is insufficient.

Install optional PaddleOCR fallback:

```bash
pip install paddleocr paddlepaddle
```

## Dashboard

```bash
streamlit run dashboard/app.py
```
