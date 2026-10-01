#!/usr/bin/env python3
"""
Convert Legacy Pipeline Output to Frontend-Ready JSON
=====================================================

CLI tool to convert existing pipeline output files to the new
frontend-optimized JSON schema.

Usage:
    python convert_to_frontend_json.py --input results/plan_X.json --output results/plan_X_frontend.json
    python convert_to_frontend_json.py --input-dir results/plan_results/ --output-dir results/frontend/
    python convert_to_frontend_json.py --input results/final_output.json --output results/frontend_output.json --full-pipeline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import directly from module file to avoid loading heavy dependencies via __init__.py
import importlib.util
_schema_path = ROOT / "pipeline" / "frontend_schema.py"
_spec = importlib.util.spec_from_file_location("pipeline.frontend_schema", _schema_path)
_frontend_schema = importlib.util.module_from_spec(_spec)
sys.modules["pipeline.frontend_schema"] = _frontend_schema
_spec.loader.exec_module(_frontend_schema)
convert_legacy_output_to_frontend = _frontend_schema.convert_legacy_output_to_frontend
SCHEMA_VERSION = _frontend_schema.SCHEMA_VERSION


def convert_single_file(
    input_path: Path,
    output_path: Path,
    include_debug: bool = False,
    verbose: bool = False,
) -> bool:
    """Convert a single legacy JSON file to frontend format."""
    try:
        with input_path.open("r", encoding="utf-8") as f:
            legacy_data = json.load(f)
        
        frontend_data = convert_legacy_output_to_frontend(
            legacy_data,
            include_debug=include_debug,
        )
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(frontend_data, f, indent=2, ensure_ascii=False)
        
        if verbose:
            rooms = sum(p["summary"]["total_rooms"] for p in frontend_data["pages"])
            print(f"  Converted: {input_path.name} -> {output_path.name} ({rooms} rooms)")
        
        return True
    except Exception as e:
        print(f"  Error converting {input_path}: {e}", file=sys.stderr)
        return False


def convert_full_pipeline_output(
    input_path: Path,
    output_path: Path,
    include_debug: bool = False,
    verbose: bool = False,
) -> bool:
    """Convert full pipeline output (final_output.json) to frontend format."""
    from datetime import datetime, timezone
    
    try:
        with input_path.open("r", encoding="utf-8") as f:
            full_output = json.load(f)
        
        # Extract plan results from full pipeline output
        plans_data = full_output.get("results", {}).get("plans", [])
        if not plans_data:
            print(f"  No plans found in {input_path}", file=sys.stderr)
            return False
        
        # Build frontend pages from embedded analysis or referenced files
        pages_data = []
        input_dir = input_path.parent
        
        for plan in plans_data:
            plan_id = plan.get("plan_id")
            source = plan.get("source", {})
            analysis = plan.get("analysis", {})
            
            # Try to get analysis data
            if isinstance(analysis, dict) and "rooms" in analysis:
                # Embedded analysis
                analysis_data = analysis
            elif "analysis_json_path" in analysis:
                # Referenced file
                analysis_path = input_dir / analysis["analysis_json_path"]
                if analysis_path.exists():
                    with analysis_path.open("r", encoding="utf-8") as f:
                        analysis_data = json.load(f)
                else:
                    if verbose:
                        print(f"  Skipping {plan_id}: analysis file not found")
                    continue
            else:
                continue
            
            # Convert to frontend format
            frontend_page = convert_legacy_output_to_frontend(
                analysis_data,
                include_debug=include_debug,
            )
            
            # Update page-specific info
            page_data = frontend_page["pages"][0]
            page_data["page_index"] = source.get("page_number", 1) - 1
            page_data["plan_id"] = plan_id
            page_data["image_path"] = str(input_dir / source.get("output_image", ""))
            
            # Update text strategy from plan text metadata
            text_info = plan.get("text", {})
            if text_info.get("text_source_used"):
                page_data["summary"]["text_strategy"] = text_info["text_source_used"]
            
            pages_data.append(page_data)
        
        # Sort pages
        pages_data.sort(key=lambda p: (p.get("page_index", 0), p.get("plan_id", "")))
        
        # Build final output
        input_info = full_output.get("input", {})
        source_file = Path(input_info.get("source_pdf", "unknown.pdf")).name
        
        frontend_output = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "type": "pdf",
                "file": source_file,
                "dpi": None,
                "total_pages": len(pages_data),
            },
            "pages": pages_data,
        }
        
        # Try to get DPI from first plan
        if plans_data:
            first_source = plans_data[0].get("source", {})
            frontend_output["source"]["dpi"] = first_source.get("dpi")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(frontend_output, f, indent=2, ensure_ascii=False)
        
        if verbose:
            total_rooms = sum(p["summary"]["total_rooms"] for p in pages_data)
            print(f"  Converted: {input_path.name} -> {output_path.name}")
            print(f"    Pages: {len(pages_data)}, Total rooms: {total_rooms}")
        
        return True
    except Exception as e:
        print(f"  Error converting {input_path}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert legacy pipeline output to frontend-ready JSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert single analysis file
  python convert_to_frontend_json.py -i results/E-01_data.json -o results/E-01_frontend.json

  # Convert full pipeline output
  python convert_to_frontend_json.py -i results/final_output.json -o results/frontend_output.json --full-pipeline

  # Convert all files in a directory
  python convert_to_frontend_json.py --input-dir results/plan_results/ --output-dir results/frontend/

  # Include debug information
  python convert_to_frontend_json.py -i results/plan.json -o results/plan_frontend.json --include-debug
        """,
    )
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-i", "--input",
        type=Path,
        help="Single input JSON file to convert",
    )
    input_group.add_argument(
        "--input-dir",
        type=Path,
        help="Directory containing JSON files to convert",
    )
    
    # Output options
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output file path (required with --input)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (required with --input-dir)",
    )
    
    # Conversion options
    parser.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Input is full pipeline output (final_output.json) with multiple plans",
    )
    parser.add_argument(
        "--include-debug",
        action="store_true",
        help="Include debug information in output (OCR tokens, text blobs)",
    )
    
    # Output options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose output",
    )
    parser.add_argument(
        "--pattern",
        default="*_data.json",
        help="File pattern for directory conversion (default: *_data.json)",
    )
    
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    
    # Validate arguments
    if args.input and not args.output:
        parser.error("--output is required when using --input")
    if args.input_dir and not args.output_dir:
        parser.error("--output-dir is required when using --input-dir")
    
    success_count = 0
    fail_count = 0
    
    if args.input:
        # Single file conversion
        if not args.input.exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            return 1
        
        if args.full_pipeline:
            success = convert_full_pipeline_output(
                args.input,
                args.output,
                include_debug=args.include_debug,
                verbose=args.verbose,
            )
        else:
            success = convert_single_file(
                args.input,
                args.output,
                include_debug=args.include_debug,
                verbose=args.verbose,
            )
        
        return 0 if success else 1
    
    else:
        # Directory conversion
        if not args.input_dir.exists():
            print(f"Error: Input directory not found: {args.input_dir}", file=sys.stderr)
            return 1
        
        files = list(args.input_dir.glob(args.pattern))
        if not files:
            print(f"No files matching '{args.pattern}' found in {args.input_dir}", file=sys.stderr)
            return 1
        
        print(f"Converting {len(files)} files...")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        
        for input_file in sorted(files):
            output_file = args.output_dir / input_file.name.replace("_data.json", "_frontend.json")
            if convert_single_file(
                input_file,
                output_file,
                include_debug=args.include_debug,
                verbose=args.verbose,
            ):
                success_count += 1
            else:
                fail_count += 1
        
        print(f"\nConversion complete: {success_count} succeeded, {fail_count} failed")
        return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
