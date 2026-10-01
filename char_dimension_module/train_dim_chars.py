"""
Train YOLOv8 character detector for floor-plan dimensions.

Usage:
  python char_dimension_module/train_dim_chars.py \
      --data char_dimension_module/datasets/dim_chars/dim_chars.yaml \
      --model yolov8n.pt --imgsz 1024 --epochs 120 --batch 16 --device 0
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train character-level YOLO detector for dimensions")
    parser.add_argument("--data", type=str, default="char_dimension_module/datasets/dim_chars/dim_chars.yaml")
    parser.add_argument("--model", type=str, default="yolov8n.pt")
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", type=str, default="0")
    parser.add_argument("--project", type=str, default="char_dimension_module/runs/detect")
    parser.add_argument("--name", type=str, default="dim_chars")
    parser.add_argument("--close-mosaic", type=int, default=10)
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("ultralytics is required: pip install ultralytics") from exc

    Path(args.project).mkdir(parents=True, exist_ok=True)
    model = YOLO(args.model)
    model.train(
        task="detect",
        data=args.data,
        imgsz=args.imgsz,
        epochs=args.epochs,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        close_mosaic=args.close_mosaic,
        pretrained=True,
    )

    print("Training complete.")
    print(f"Best weights: {Path(args.project) / args.name / 'weights' / 'best.pt'}")


if __name__ == "__main__":
    main()
