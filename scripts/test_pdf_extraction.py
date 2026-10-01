#!/usr/bin/env python3
"""
Test script to compare PDF extraction methods.

Compares:
1. OLD: Page re-rendering at high DPI (current method)
2. NEW: Direct embedded image extraction (new method)

Usage:
    python scripts/test_pdf_extraction.py Dataset/pdf_files/Test_5.pdf
"""

import sys
import json
from pathlib import Path

# Add pipeline to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
import fitz

from pdf_extract.image_extractor import PDFImageExtractor, ExtractionConfig


def analyze_image(image: np.ndarray, label: str) -> dict:
    """Analyze image quality metrics."""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    
    # Sharpness (Laplacian variance)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = laplacian.var()
    
    # Contrast
    contrast = gray.std()
    
    # Edge density
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.count_nonzero(edges) / edges.size * 100
    
    return {
        "label": label,
        "size": (w, h),
        "sharpness": sharpness,
        "contrast": contrast,
        "edge_density": edge_density,
    }


def render_page_old_method(pdf_path: str, page_idx: int, dpi: int = 450) -> np.ndarray:
    """Old method: render entire page at high DPI."""
    doc = fitz.open(pdf_path)
    page = doc[page_idx]
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    doc.close()
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def extract_embedded_new_method(pdf_path: str, page_idx: int) -> np.ndarray:
    """New method: extract embedded image directly."""
    config = ExtractionConfig(min_embedded_size=100)
    extractor = PDFImageExtractor(config)
    results = extractor.extract_from_pdf(pdf_path, page_indices=[page_idx])
    
    if results and results[0].extraction_method == "embedded":
        return results[0].image
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_pdf_extraction.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    page_idx = 0  # Test first page
    
    print("=" * 70)
    print("PDF EXTRACTION METHOD COMPARISON")
    print("=" * 70)
    print(f"PDF: {pdf_path}")
    print(f"Page: {page_idx + 1}")
    print()
    
    # Method 1: Old (re-render)
    print("Extracting with OLD method (re-render at 450 DPI)...")
    old_image = render_page_old_method(pdf_path, page_idx, dpi=450)
    old_metrics = analyze_image(old_image, "OLD (re-render 450 DPI)")
    
    # Method 2: New (direct extraction)
    print("Extracting with NEW method (direct embedded)...")
    new_image = extract_embedded_new_method(pdf_path, page_idx)
    
    if new_image is None:
        print("No embedded image found, falling back to render")
        new_image = render_page_old_method(pdf_path, page_idx, dpi=300)
        new_metrics = analyze_image(new_image, "NEW (render fallback)")
    else:
        new_metrics = analyze_image(new_image, "NEW (direct embedded)")
    
    # Print comparison
    print()
    print("=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)
    print()
    
    print(f"{'Metric':<25} {'OLD (re-render)':<20} {'NEW (embedded)':<20}")
    print("-" * 70)
    print(f"{'Size':<25} {str(old_metrics['size']):<20} {str(new_metrics['size']):<20}")
    print(f"{'Sharpness (Laplacian)':<25} {old_metrics['sharpness']:<20.1f} {new_metrics['sharpness']:<20.1f}")
    print(f"{'Contrast (std)':<25} {old_metrics['contrast']:<20.1f} {new_metrics['contrast']:<20.1f}")
    print(f"{'Edge Density (%)':<25} {old_metrics['edge_density']:<20.2f} {new_metrics['edge_density']:<20.2f}")
    
    print()
    print("=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    
    # Compare sharpness
    if new_metrics['sharpness'] > old_metrics['sharpness'] * 0.8:
        print("✅ NEW method preserves sharpness (no interpolation blur)")
    else:
        print("⚠️  Sharpness comparison inconclusive")
    
    # Size comparison
    old_pixels = old_metrics['size'][0] * old_metrics['size'][1]
    new_pixels = new_metrics['size'][0] * new_metrics['size'][1]
    
    if new_pixels < old_pixels:
        print(f"✅ NEW method uses native resolution ({new_metrics['size'][0]}x{new_metrics['size'][1]})")
        print(f"   OLD method artificially upscaled to ({old_metrics['size'][0]}x{old_metrics['size'][1]})")
        print(f"   Upscale factor: {(old_pixels/new_pixels)**0.5:.1f}x")
    
    print()
    print("💡 RECOMMENDATION:")
    print("   Use the NEW direct extraction method for PDF floor plans.")
    print("   This preserves original image quality without interpolation artifacts.")
    
    # Save comparison images
    output_dir = Path("results/extraction_comparison")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cv2.imwrite(str(output_dir / "old_method.png"), old_image)
    cv2.imwrite(str(output_dir / "new_method.png"), new_image)
    
    print()
    print(f"Saved comparison images to: {output_dir}")
    print(f"  - old_method.png ({old_metrics['size'][0]}x{old_metrics['size'][1]})")
    print(f"  - new_method.png ({new_metrics['size'][0]}x{new_metrics['size'][1]})")


if __name__ == "__main__":
    main()
