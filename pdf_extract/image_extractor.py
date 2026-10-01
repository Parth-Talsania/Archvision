"""
PDF Image Extractor - Extract-First, Render-Fallback Strategy

This module extracts floor plan images from PDFs using a two-tier approach:
1. PRIORITY: Extract embedded raster images at their native quality
2. FALLBACK: Render page at high DPI (for vector-only PDFs)

This preserves original image quality and avoids degradation from re-rendering.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
import json
import logging

import cv2
import numpy as np

try:
    import fitz  # PyMuPDF
except ImportError as exc:
    raise ImportError(
        "PyMuPDF is required. Install with: pip install pymupdf"
    ) from exc

logger = logging.getLogger(__name__)


@dataclass
class ExtractedImage:
    """Represents an extracted floor plan image."""
    image: np.ndarray
    page_index: int
    extraction_method: str  # "embedded" or "rendered"
    source_format: str  # "jpeg", "png", "rendered"
    native_size: Tuple[int, int]  # (width, height)
    final_size: Tuple[int, int]  # After any processing
    bbox_on_page: Optional[Tuple[float, float, float, float]] = None  # PDF points
    quality_score: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass 
class ExtractionConfig:
    """Configuration for PDF image extraction."""
    # Embedded image extraction settings
    min_embedded_size: int = 400  # Minimum dimension to consider embedded image
    min_embedded_area_ratio: float = 0.1  # Min area ratio vs page size
    
    # Fallback rendering settings
    render_dpi: int = 300  # DPI for page rendering fallback
    target_long_side: int = 2048  # Target size for rendered images
    
    # Quality thresholds
    min_quality_score: float = 0.3  # Minimum score to accept extraction
    
    # Output settings
    output_format: str = "png"  # Output format for saved images
    save_debug: bool = False  # Save debug comparison images


class PDFImageExtractor:
    """
    Extract floor plan images from PDFs using Extract-First strategy.
    
    Prioritizes direct extraction of embedded images to preserve quality,
    falling back to page rendering only for vector-based PDFs.
    """
    
    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
    
    def extract_from_pdf(
        self,
        pdf_path: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        page_indices: Optional[List[int]] = None,
    ) -> List[ExtractedImage]:
        """
        Extract floor plan images from a PDF.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted images (optional)
            page_indices: Specific pages to process (0-indexed), or None for all
            
        Returns:
            List of ExtractedImage objects
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        doc = fitz.open(str(pdf_path))
        
        if page_indices is None:
            page_indices = list(range(len(doc)))
        
        results: List[ExtractedImage] = []
        
        for page_idx in page_indices:
            if page_idx >= len(doc):
                logger.warning(f"Page index {page_idx} out of range, skipping")
                continue
            
            page = doc[page_idx]
            
            # PRIORITY 1: Try to extract embedded images
            embedded = self._extract_embedded_images(doc, page, page_idx)
            
            if embedded:
                # Found embedded images - use them
                for img in embedded:
                    img.quality_score = self._score_image_quality(img.image)
                    if img.quality_score >= self.config.min_quality_score:
                        results.append(img)
                        logger.info(
                            f"Page {page_idx+1}: Extracted embedded {img.source_format} "
                            f"{img.native_size[0]}x{img.native_size[1]} (score: {img.quality_score:.2f})"
                        )
            
            # FALLBACK: If no good embedded images, render the page
            if not any(r.page_index == page_idx for r in results):
                rendered = self._render_page(page, page_idx)
                rendered.quality_score = self._score_image_quality(rendered.image)
                results.append(rendered)
                logger.info(
                    f"Page {page_idx+1}: Rendered at {self.config.render_dpi} DPI "
                    f"{rendered.final_size[0]}x{rendered.final_size[1]} (score: {rendered.quality_score:.2f})"
                )
        
        doc.close()
        
        # Save images if output directory specified
        if output_dir:
            self._save_results(results, pdf_path, output_dir)
        
        return results
    
    def _extract_embedded_images(
        self,
        doc: fitz.Document,
        page: fitz.Page,
        page_idx: int,
    ) -> List[ExtractedImage]:
        """Extract embedded raster images from a PDF page."""
        results = []
        
        images = page.get_images(full=True)
        if not images:
            return results
        
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height
        
        for img_info in images:
            xref = img_info[0]
            
            try:
                # Extract raw image bytes
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                width = base_image["width"]
                height = base_image["height"]
                img_format = base_image["ext"]
                
                # Check minimum size
                if min(width, height) < self.config.min_embedded_size:
                    logger.debug(f"Skipping small image: {width}x{height}")
                    continue
                
                # Decode image
                img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                
                if image is None:
                    logger.warning(f"Failed to decode image xref={xref}")
                    continue
                
                # Get bounding box on page
                try:
                    bbox = page.get_image_bbox(img_info)
                    bbox_tuple = (bbox.x0, bbox.y0, bbox.x1, bbox.y1)
                    
                    # Check area ratio
                    img_area = bbox.width * bbox.height
                    area_ratio = img_area / page_area if page_area > 0 else 0
                    
                    if area_ratio < self.config.min_embedded_area_ratio:
                        logger.debug(f"Skipping small area image: {area_ratio:.2%}")
                        continue
                        
                except Exception:
                    bbox_tuple = None
                
                results.append(ExtractedImage(
                    image=image,
                    page_index=page_idx,
                    extraction_method="embedded",
                    source_format=img_format,
                    native_size=(width, height),
                    final_size=(image.shape[1], image.shape[0]),
                    bbox_on_page=bbox_tuple,
                    metadata={"xref": xref, "colorspace": base_image.get("colorspace", "unknown")},
                ))
                
            except Exception as e:
                logger.warning(f"Failed to extract image xref={xref}: {e}")
                continue
        
        return results
    
    def _render_page(self, page: fitz.Page, page_idx: int) -> ExtractedImage:
        """Render a PDF page to an image (fallback for vector PDFs)."""
        dpi = self.config.render_dpi
        scale = dpi / 72.0
        
        # Render with white background (alpha=False)
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Convert to numpy array
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, 3
        )
        image = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        native_size = (pix.width, pix.height)
        
        # Optionally resize to target size
        h, w = image.shape[:2]
        long_side = max(h, w)
        target = self.config.target_long_side
        
        if target > 0 and long_side > target:
            scale_factor = target / long_side
            new_w = int(w * scale_factor)
            new_h = int(h * scale_factor)
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        final_size = (image.shape[1], image.shape[0])
        
        return ExtractedImage(
            image=image,
            page_index=page_idx,
            extraction_method="rendered",
            source_format="rendered",
            native_size=native_size,
            final_size=final_size,
            bbox_on_page=None,
            metadata={"dpi": dpi, "scale": scale},
        )
    
    def _score_image_quality(self, image: np.ndarray) -> float:
        """
        Score image quality for floor plan detection.
        
        Considers:
        - Edge sharpness (Laplacian variance)
        - Contrast
        - Size adequacy
        """
        h, w = image.shape[:2]
        
        # Size score (prefer larger images up to a point)
        min_dim = min(h, w)
        size_score = min(1.0, min_dim / 800.0)
        
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        
        # Sharpness score (Laplacian variance)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = laplacian.var()
        # Normalize: typical range 100-2000 for floor plans
        sharpness_score = min(1.0, sharpness / 500.0)
        
        # Contrast score
        contrast = gray.std()
        # Normalize: typical range 30-80 for floor plans
        contrast_score = min(1.0, contrast / 50.0)
        
        # Weighted combination
        score = 0.3 * size_score + 0.4 * sharpness_score + 0.3 * contrast_score
        
        return float(np.clip(score, 0.0, 1.0))
    
    def _save_results(
        self,
        results: List[ExtractedImage],
        pdf_path: Path,
        output_dir: Union[str, Path],
    ) -> Dict:
        """Save extracted images and manifest."""
        output_dir = Path(output_dir)
        floorplans_dir = output_dir / "floorplans"
        floorplans_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_stem = pdf_path.stem
        manifest_entries = []
        
        for idx, result in enumerate(results):
            # Generate filename
            page_num = result.page_index + 1
            suffix = f"_e{idx+1}" if result.extraction_method == "embedded" else ""
            filename = f"{pdf_stem}_p{page_num:02d}{suffix}.{self.config.output_format}"
            filepath = floorplans_dir / filename
            
            # Save image
            cv2.imwrite(str(filepath), result.image)
            
            # Manifest entry
            manifest_entries.append({
                "filename": filename,
                "path": str(filepath),
                "page": page_num,
                "extraction_method": result.extraction_method,
                "source_format": result.source_format,
                "native_size": list(result.native_size),
                "final_size": list(result.final_size),
                "quality_score": round(result.quality_score, 3),
                "bbox_on_page": list(result.bbox_on_page) if result.bbox_on_page else None,
            })
        
        # Save manifest
        manifest = {
            "pdf": str(pdf_path),
            "pdf_name": pdf_path.name,
            "total_extracted": len(results),
            "embedded_count": sum(1 for r in results if r.extraction_method == "embedded"),
            "rendered_count": sum(1 for r in results if r.extraction_method == "rendered"),
            "images": manifest_entries,
        }
        
        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Saved {len(results)} images to {floorplans_dir}")
        
        return manifest


def extract_pdf_images(
    pdf_path: Union[str, Path],
    output_dir: Union[str, Path],
    config: Optional[ExtractionConfig] = None,
) -> Dict:
    """
    Convenience function to extract images from a PDF.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images
        config: Extraction configuration (optional)
        
    Returns:
        Manifest dictionary with extraction results
    """
    extractor = PDFImageExtractor(config)
    results = extractor.extract_from_pdf(pdf_path, output_dir)
    
    # Return manifest-like dict
    return {
        "pdf": str(pdf_path),
        "total_extracted": len(results),
        "images": [
            {
                "page": r.page_index + 1,
                "method": r.extraction_method,
                "size": r.final_size,
                "score": r.quality_score,
            }
            for r in results
        ],
    }


# CLI entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract floor plan images from PDF")
    parser.add_argument("pdf", help="Path to PDF file")
    parser.add_argument("-o", "--output", required=True, help="Output directory")
    parser.add_argument("--min-size", type=int, default=400, help="Minimum embedded image size")
    parser.add_argument("--render-dpi", type=int, default=300, help="DPI for rendered fallback")
    parser.add_argument("--debug", action="store_true", help="Save debug images")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    config = ExtractionConfig(
        min_embedded_size=args.min_size,
        render_dpi=args.render_dpi,
        save_debug=args.debug,
    )
    
    result = extract_pdf_images(args.pdf, args.output, config)
    print(f"\nExtracted {result['total_extracted']} images from {result['pdf']}")
    for img in result["images"]:
        print(f"  Page {img['page']}: {img['method']} {img['size'][0]}x{img['size'][1]} (score: {img['score']:.2f})")
