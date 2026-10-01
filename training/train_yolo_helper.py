from __future__ import annotations

import argparse

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLOv8-seg model for floor-plan rooms.")
    parser.add_argument("--data", required=True, help="Path to data.yaml")
    parser.add_argument("--model", default="yolov8s-seg.pt", help="Base model")
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--project", default="runs/segment")
    parser.add_argument("--name", default="floor_plan_rooms_v2")
    args = parser.parse_args()

    model = YOLO(args.model)
    model.train(
        data=args.data,
        imgsz=args.imgsz,
        epochs=args.epochs,
        batch=args.batch,
        project=args.project,
        name=args.name,
        task="segment",
        cache=True,
        close_mosaic=10,
        hsv_h=0.01,
        hsv_s=0.4,
        hsv_v=0.25,
        translate=0.05,
        scale=0.2,
        fliplr=0.5,
        degrees=7.0,
        perspective=0.0006,
    )


if __name__ == "__main__":
    main()
