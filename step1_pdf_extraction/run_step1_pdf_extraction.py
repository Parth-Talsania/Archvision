"""
Step-1 runner (no argparse).

Edit CONFIG, then run:
    python step1_pdf_extraction/run_step1_pdf_extraction.py
"""

from pathlib import Path

from brochure_pdf_extractor import BrochureFloorPlanExtractor


CONFIG = {
    # Fill this when a brochure PDF is available
    "pdf_path": "",
    "model_path": "",
    "output_dir": "results/step1_pdf_output",
    "dpi": 300,
    "min_score": 0.35,
    "top_k": 3,
    "trim_border": True,
    "yolo_conf": 0.25,
    "yolo_iou": 0.5,
    "yolo_imgsz": 1024,
    "min_area_ratio": 0.03,
    "min_det_area_ratio": 0.001,
    "min_component_detections": 4,
    "component_close_kernel": 31,
    "top_k_per_page": 2,
    "crop_padding": 10,
    "save_debug": True,
    "device": "auto",
}


def main() -> None:
    pdf_path = CONFIG["pdf_path"]
    if not pdf_path:
        raise ValueError("Set CONFIG['pdf_path'] before running Step-1 extraction.")
    if not CONFIG["model_path"]:
        raise ValueError("Set CONFIG['model_path'] (best.pt) before running Step-1 extraction.")

    extractor = BrochureFloorPlanExtractor(
        yolo_model_path=CONFIG["model_path"],
        dpi=CONFIG["dpi"],
        min_score=CONFIG["min_score"],
        top_k=CONFIG["top_k"],
        trim_border=CONFIG["trim_border"],
        yolo_conf=CONFIG["yolo_conf"],
        yolo_iou=CONFIG["yolo_iou"],
        yolo_imgsz=CONFIG["yolo_imgsz"],
        min_area_ratio=CONFIG["min_area_ratio"],
        min_det_area_ratio=CONFIG["min_det_area_ratio"],
        min_component_detections=CONFIG["min_component_detections"],
        component_close_kernel=CONFIG["component_close_kernel"],
        top_k_per_page=CONFIG["top_k_per_page"],
        crop_padding=CONFIG["crop_padding"],
        save_debug=CONFIG["save_debug"],
        device=CONFIG["device"],
    )
    manifest = extractor.extract_floorplan_pages(
        pdf_path=Path(pdf_path),
        output_dir=Path(CONFIG["output_dir"]),
    )

    print("\n=== STEP-1 COMPLETE ===")
    print(f"PDF: {manifest['pdf_path']}")
    print(f"Pages: {manifest['total_pages']}")
    print(f"Selected images: {len(manifest['selected_images'])}")
    for path in manifest["selected_images"]:
        print(f"  - {path}")
    print(f"Manifest: {Path(CONFIG['output_dir']) / 'step1_manifest.json'}")


if __name__ == "__main__":
    main()
