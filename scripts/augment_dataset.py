from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import List, Tuple

import albumentations as A
import cv2
import numpy as np


def load_yolo_seg_labels(label_path: Path, width: int, height: int) -> Tuple[List[List[Tuple[float, float]]], List[int]]:
    polygons: List[List[Tuple[float, float]]] = []
    classes: List[int] = []
    if not label_path.exists():
        return polygons, classes
    lines = label_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 7:
            continue
        cls = int(float(parts[0]))
        vals = [float(x) for x in parts[1:]]
        pts = []
        for i in range(0, len(vals), 2):
            x = vals[i] * width
            y = vals[i + 1] * height
            pts.append((x, y))
        if len(pts) >= 3:
            polygons.append(pts)
            classes.append(cls)
    return polygons, classes


def save_yolo_seg_labels(label_path: Path, polygons: List[List[Tuple[float, float]]], classes: List[int], width: int, height: int) -> None:
    out_lines: List[str] = []
    for cls, poly in zip(classes, polygons):
        pts_norm: List[str] = []
        for x, y in poly:
            xn = min(1.0, max(0.0, float(x) / max(1, width)))
            yn = min(1.0, max(0.0, float(y) / max(1, height)))
            pts_norm.append(f"{xn:.6f}")
            pts_norm.append(f"{yn:.6f}")
        if len(pts_norm) >= 6:
            out_lines.append(f"{cls} {' '.join(pts_norm)}")
    label_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.write_text("\n".join(out_lines), encoding="utf-8")


def overlay_watermark(image: np.ndarray) -> np.ndarray:
    out = image.copy()
    h, w = out.shape[:2]
    txt = random.choice(["SAMPLE PLAN", "NOT FOR CONSTRUCTION", "DRAFT", "WATERMARK"])
    overlay = out.copy()
    cv2.putText(overlay, txt, (max(10, w // 6), max(30, h // 2)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (150, 150, 150), 2, cv2.LINE_AA)
    alpha = random.uniform(0.12, 0.28)
    cv2.addWeighted(overlay, alpha, out, 1 - alpha, 0, out)
    return out


def break_lines_simulation(image: np.ndarray) -> np.ndarray:
    out = image.copy()
    h, w = out.shape[:2]
    for _ in range(random.randint(8, 25)):
        x1 = random.randint(0, max(0, w - 1))
        y1 = random.randint(0, max(0, h - 1))
        x2 = min(w - 1, x1 + random.randint(4, 20))
        y2 = y1 + random.randint(-1, 1)
        cv2.line(out, (x1, y1), (x2, y2), (255, 255, 255), thickness=random.randint(1, 2))
    return out


def build_transform() -> A.Compose:
    return A.Compose(
        [
            A.Affine(scale=(0.95, 1.05), rotate=(-15, 15), shear=(-4, 4), p=0.7),
            A.Perspective(scale=(0.02, 0.07), p=0.3),
            A.GaussNoise(p=0.25),
            A.GaussianBlur(blur_limit=(3, 5), p=0.2),
            A.RandomBrightnessContrast(brightness_limit=0.18, contrast_limit=0.22, p=0.35),
            A.ToGray(p=0.12),
        ],
        polygon_params=A.PolygonParams(format="xy", label_fields=["class_labels"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Augment YOLO segmentation dataset for floor plans.")
    parser.add_argument("--images-dir", required=True)
    parser.add_argument("--labels-dir", required=True)
    parser.add_argument("--out-images-dir", required=True)
    parser.add_argument("--out-labels-dir", required=True)
    parser.add_argument("--copies", type=int, default=2, help="Augmented copies per source image")
    args = parser.parse_args()

    img_dir = Path(args.images_dir)
    lbl_dir = Path(args.labels_dir)
    out_img_dir = Path(args.out_images_dir)
    out_lbl_dir = Path(args.out_labels_dir)
    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_lbl_dir.mkdir(parents=True, exist_ok=True)

    tfm = build_transform()
    exts = {".png", ".jpg", ".jpeg"}
    images = sorted([p for p in img_dir.iterdir() if p.suffix.lower() in exts])
    total_written = 0
    for img_path in images:
        image = cv2.imread(str(img_path))
        if image is None:
            continue
        h, w = image.shape[:2]
        label_path = lbl_dir / f"{img_path.stem}.txt"
        polys, classes = load_yolo_seg_labels(label_path, w, h)
        if not polys:
            continue
        for copy_idx in range(args.copies):
            transformed = tfm(image=image, polygons=polys, class_labels=classes)
            aug_img = transformed["image"]
            aug_polys = transformed["polygons"]
            aug_classes = transformed["class_labels"]
            if random.random() < 0.35:
                aug_img = overlay_watermark(aug_img)
            if random.random() < 0.25:
                aug_img = break_lines_simulation(aug_img)
            ah, aw = aug_img.shape[:2]
            valid_polys: List[List[Tuple[float, float]]] = []
            valid_classes: List[int] = []
            for cls, poly in zip(aug_classes, aug_polys):
                if len(poly) < 3:
                    continue
                clipped = [(min(max(0.0, float(x)), aw - 1.0), min(max(0.0, float(y)), ah - 1.0)) for x, y in poly]
                if len(clipped) >= 3:
                    valid_polys.append(clipped)
                    valid_classes.append(int(cls))
            if not valid_polys:
                continue
            out_stem = f"{img_path.stem}_aug{copy_idx + 1:02d}"
            out_img_path = out_img_dir / f"{out_stem}.jpg"
            out_lbl_path = out_lbl_dir / f"{out_stem}.txt"
            cv2.imwrite(str(out_img_path), aug_img)
            save_yolo_seg_labels(out_lbl_path, valid_polys, valid_classes, aw, ah)
            total_written += 1
    print(f"[DONE] Wrote {total_written} augmented samples")


if __name__ == "__main__":
    main()
