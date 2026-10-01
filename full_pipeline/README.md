# Full Pipeline (Merged)

End-to-end command:

1. Extract floor plan crops from input PDF.
2. Analyze each extracted plan with v2 segmentation + OCR.
3. Produce one combined `final_output.json`.

## Command

```bash
python -m full_pipeline.run ^
  --pdf "Dataset/PDF/Test_2.pdf" ^
  --out_dir "results/full_merged_test2" ^
  --yolo_model "results/runs/segment/runs/segment/floor_plan_rooms/weights/best.pt" ^
  --text-source auto --ocr-engine paddle --save-text-debug ^
  --save_debug_extractor --save_debug_analyzer
```

## Integration Plan

- Extractor API called: `full_pipeline.extractor_api.extract_floorplans_from_pdf`
- Analyzer API called: `full_pipeline.analyzer_api.analyze_floorplan_image` (or cached runner)
- Orchestrator: `full_pipeline.orchestrator.run_full_pipeline`
- The orchestrator passes extractor crop paths into analyzer and writes standardized outputs.

## Output Layout

```text
OUTPUT_DIR/
  extracted_plans/
    manifest_extraction.json
    floorplans/
      <pdf_stem>_p013_r01.png
      ...
  plan_results/
    plan_<plan_id>.json
    plan_<plan_id>_viz.png
  final_output.json
  logs/
    run.log
  debug/
    extractor/...
    analyzer/<plan_id>/...
    index.json
```

## Coordinate Mapping

Each plan entry in `final_output.json` includes:
- `bbox_px_page`: crop bounding box in rendered page coordinates
- `dpi`
- `coordinate_frames.px_per_pdf_point = dpi / 72`

Mapping:
- `page_px = plan_px + (bbox.x1, bbox.y1)`
- `pdf_points = page_px / (dpi/72)`

Optional:
- `--export-polygons-page-coords` augments room polygons with page/pdf coordinates.

## Key Flags

- `--resume`
- `--embed-analysis-json`
- `--workers` (CPU only; auto-forced to 1 for GPU mode)
- `--max_plans`
- `--stop-on-first-failure`
- `--save_debug_extractor`
- `--save_debug_analyzer`
- `--text-source auto|pdf|ocr`
- `--ocr-engine paddle|easyocr`
- `--ocr-dpi 600`
- `--min-pdf-words 8`
- `--save-text-debug`

Optional install for PaddleOCR fallback:

```bash
pip install paddleocr paddlepaddle
```
