# Step-1 PDF Floor Plan Extraction

This module extracts likely floor-plan pages from brochure PDFs at high resolution.

## Files
- `step1_pdf_extraction/brochure_pdf_extractor.py`
- `step1_pdf_extraction/run_step1_pdf_extraction.py`

## Install
```bash
pip install pymupdf opencv-python numpy
```

## Run
1. Open `step1_pdf_extraction/run_step1_pdf_extraction.py`
2. Set `CONFIG["pdf_path"]` and optionally output/scoring settings
3. Run:
```bash
python step1_pdf_extraction/run_step1_pdf_extraction.py
```

## Outputs
- Selected page images in `CONFIG["output_dir"]`
- Manifest: `step1_manifest.json` with:
  - page scores
  - selected pages
  - exported image paths

These exported images can be passed directly into Step-2 (`floor_plan_pipeline.py`).

