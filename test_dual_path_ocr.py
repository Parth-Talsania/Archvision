#!/usr/bin/env python3
"""
Test script for dual-path OCR implementation.
This demonstrates the specialized dimension extraction for scanned PDFs.
"""

import os
from pathlib import Path
from floor_plan_pipeline import FloorPlanAnalyzer

def main():
    # Configuration
    MODEL_PATH = "/kaggle/input/datasets/parthtalsania/final-floor-yolo/runs/segment/runs/segment/floor_plan_rooms/weights/best.pt"
    PDF_PATH = "/kaggle/input/datasets/parthtalsania/floor-dataset/Dataset/PDF/Test_5.pdf"
    OUTPUT_DIR = "/kaggle/working"
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 80)
    print("DUAL-PATH OCR TEST FOR SCANNED PDFs")
    print("=" * 80)
    print("This test uses:")
    print("  - YOLO DPI: 300 (fast room detection)")
    print("  - OCR DPI: 600 (sharp text for dimensions)")
    print("  - Labels: Global OCR (no restrictions)")
    print("  - Dimensions: Per-room OCR (allowlist + 2-pass preprocessing)")
    print("=" * 80)
    
    # Initialize analyzer
    analyzer = FloorPlanAnalyzer(model_path=MODEL_PATH, use_gpu=True)
    
    # Run analysis with dual-path OCR
    results = analyzer.analyze(
        image_path=PDF_PATH,
        pdf_max_pages=0,  # Process ALL pages
        dpi_yolo=300,     # Lower DPI for YOLO (faster)
        dpi_ocr=600,      # Higher DPI for OCR (sharper text)
        use_per_room_ocr=True,    # Enable dual-path strategy
        show_dimensions=True,     # Show dimensions on visualization
        debug_save_room_crops=True,  # Save debug crops for inspection
        visualize=True,
        output_path=f"{OUTPUT_DIR}/test5_dual_path_result.png",
        return_pages=True,
    )
    
    # Print results
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    
    if "pages" in results:
        total_rooms = 0
        total_with_labels = 0
        total_with_dimensions = 0
        
        for page_idx, page in enumerate(results["pages"], 1):
            summary = page["summary"]
            rooms = page["rooms"]
            
            print(f"\nPAGE {page_idx}:")
            print(f"  Strategy: {summary['text_extraction_strategy']}")
            print(f"  Rooms detected: {summary['total_rooms']}")
            print(f"  Rooms with labels: {summary['rooms_with_labels']}")
            print(f"  Rooms with dimensions: {summary['rooms_with_dimensions']}")
            
            total_rooms += summary['total_rooms']
            total_with_labels += summary['rooms_with_labels']
            total_with_dimensions += summary['rooms_with_dimensions']
            
            # Show room details
            print("  Room details:")
            for i, room in enumerate(rooms, 1):
                label = room.get('label', 'N/A')
                dim = room.get('dimensions', 'N/A')
                source = room.get('dimension_source', 'N/A')
                print(f"    Room {i}: {label} | {dim} (source: {source})")
    
        print(f"\n" + "=" * 80)
        print("OVERALL SUMMARY:")
        print(f"  Total rooms: {total_rooms}")
        print(f"  With labels: {total_with_labels}/{total_rooms} ({100*total_with_labels/total_rooms:.1f}%)")
        print(f"  With dimensions: {total_with_dimensions}/{total_rooms} ({100*total_with_dimensions/total_rooms:.1f}%)")
        print("=" * 80)
        
        # Save detailed JSON report
        import json
        report_path = f"{OUTPUT_DIR}/dual_path_test_report.json"
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nDetailed report saved to: {report_path}")
        print(f"Visualization saved to: {OUTPUT_DIR}/test5_dual_path_result.png")
        print(f"Debug crops saved to: {OUTPUT_DIR}/debug_crops/")
        
    else:
        print("No pages found in results")

if __name__ == "__main__":
    main()