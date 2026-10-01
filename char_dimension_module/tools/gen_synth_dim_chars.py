"""
Generate synthetic character-level dimension dataset for YOLO.

Usage:
  python char_dimension_module/tools/gen_synth_dim_chars.py --out char_dimension_module/datasets/dim_chars --train 5000 --val 500

This creates:
  images/train, images/val, labels/train, labels/val
and writes one YOLO box per character.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


CLASS_NAMES: List[str] = [
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "apostrophe", "quote", "slash", "dash", "x", "dot", "times", "half", "quarter", "three_quarter",
]

CHAR_TO_CLASS: Dict[str, str] = {
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
    "'": "apostrophe", '"': "quote", "/": "slash", "-": "dash", "x": "x", "X": "x", ".": "dot", "*": "times", "\u00d7": "times",
    "\u00bd": "half", "\u00bc": "quarter", "\u00be": "three_quarter",
}

CLASS_TO_ID: Dict[str, int] = {n: i for i, n in enumerate(CLASS_NAMES)}


@dataclass
class CharBox:
    cls_id: int
    x1: float
    y1: float
    x2: float
    y2: float


def _find_fonts(font_dir: Path) -> List[Path]:
    fonts = sorted(font_dir.glob("*.ttf")) + sorted(font_dir.glob("*.otf"))
    return [f for f in fonts if f.is_file()]


def _random_fraction_token() -> str:
    choices = ["", " 1/2", " 1/4", " 3/4", "\u00bd", "\u00bc", "\u00be"]
    weights = [0.48, 0.18, 0.12, 0.12, 0.04, 0.03, 0.03]
    return random.choices(choices, weights=weights, k=1)[0]


def _make_measurement_variant() -> str:
    feet = random.randint(6, 24)
    inches = random.randint(0, 11)
    frac = _random_fraction_token()

    variants = [
        f"{feet}'-{inches}{frac}\"",
        f"{feet}'{inches}{frac}\"",
        f"{feet}' {inches}{frac}\"",
        f"{feet}'-{inches}-{frac.strip()}\"" if frac.strip() else f"{feet}'-{inches}\"",
        f"{feet}'-{inches}\"",
    ]
    text = random.choice(variants)
    text = text.replace("--", "-").replace("  ", " ")
    return text


def _make_dimension_text() -> str:
    if random.random() < 0.35:
        return _make_measurement_variant()

    sep = random.choice([" x ", " X ", " \u00d7 "])
    return f"{_make_measurement_variant()}{sep}{_make_measurement_variant()}"


def _load_font(fonts: Sequence[Path], size: int) -> ImageFont.FreeTypeFont:
    if fonts:
        fp = random.choice(fonts)
        return ImageFont.truetype(str(fp), size=size)
    return ImageFont.load_default()


def _render_chars(text: str, canvas_w: int, canvas_h: int, fonts: Sequence[Path]) -> Tuple[np.ndarray, List[CharBox]]:
    text_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    font_size = int(np.clip(np.random.normal(loc=15.0, scale=4.0), 10, 28))
    font = _load_font(fonts, font_size)

    x = random.randint(6, max(6, canvas_w // 4))
    y = random.randint(6, max(6, canvas_h // 2))

    boxes: List[CharBox] = []
    for ch in text:
        if ch == " ":
            x += max(2, font_size // 3)
            continue

        bbox = draw.textbbox((x, y), ch, font=font)
        draw.text((x, y), ch, font=font, fill=(20, 20, 20, 255))

        cls_name = CHAR_TO_CLASS.get(ch)
        if cls_name is not None:
            boxes.append(CharBox(cls_id=CLASS_TO_ID[cls_name], x1=float(bbox[0]), y1=float(bbox[1]), x2=float(bbox[2]), y2=float(bbox[3])))

        x += int(font.getlength(ch)) if hasattr(font, "getlength") else max(4, (bbox[2] - bbox[0]))

    return np.array(text_layer), boxes


def _transform_boxes_rotate(boxes: Sequence[CharBox], angle_deg: float, cx: float, cy: float) -> List[CharBox]:
    a = np.deg2rad(angle_deg)
    cos_a, sin_a = np.cos(a), np.sin(a)

    out: List[CharBox] = []
    for b in boxes:
        pts = np.array([[b.x1, b.y1], [b.x2, b.y1], [b.x2, b.y2], [b.x1, b.y2]], dtype=np.float32)
        pts[:, 0] -= cx
        pts[:, 1] -= cy
        rot = np.zeros_like(pts)
        rot[:, 0] = pts[:, 0] * cos_a - pts[:, 1] * sin_a
        rot[:, 1] = pts[:, 0] * sin_a + pts[:, 1] * cos_a
        rot[:, 0] += cx
        rot[:, 1] += cy
        x1, y1 = float(np.min(rot[:, 0])), float(np.min(rot[:, 1]))
        x2, y2 = float(np.max(rot[:, 0])), float(np.max(rot[:, 1]))
        out.append(CharBox(cls_id=b.cls_id, x1=x1, y1=y1, x2=x2, y2=y2))
    return out


def _background(canvas_h: int, canvas_w: int, bg_dir: Path) -> np.ndarray:
    if bg_dir.exists():
        bg_files = sorted([p for p in bg_dir.glob("*.*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}])
        if bg_files and random.random() < 0.5:
            img = cv2.imread(str(random.choice(bg_files)))
            if img is not None and img.shape[0] > 10 and img.shape[1] > 10:
                y0 = random.randint(0, max(0, img.shape[0] - canvas_h))
                x0 = random.randint(0, max(0, img.shape[1] - canvas_w))
                patch = img[y0:y0 + canvas_h, x0:x0 + canvas_w]
                if patch.shape[0] == canvas_h and patch.shape[1] == canvas_w:
                    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
                    gray = cv2.normalize(gray, None, 200, 255, cv2.NORM_MINMAX)
                    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    val = random.randint(225, 255)
    return np.full((canvas_h, canvas_w, 3), val, dtype=np.uint8)


def _augment(img: np.ndarray) -> np.ndarray:
    out = img.copy()

    if random.random() < 0.8:
        alpha = random.uniform(0.85, 1.2)
        beta = random.uniform(-12, 12)
        out = cv2.convertScaleAbs(out, alpha=alpha, beta=beta)

    if random.random() < 0.5:
        k = random.choice([3, 3, 5])
        out = cv2.GaussianBlur(out, (k, k), sigmaX=random.uniform(0.1, 1.1))

    if random.random() < 0.5:
        noise = np.random.normal(0, random.uniform(2, 12), out.shape).astype(np.int16)
        out = np.clip(out.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    if random.random() < 0.35:
        g = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
        th = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 19, random.randint(2, 8))
        out = cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)

    if random.random() < 0.35:
        quality = random.randint(45, 90)
        enc = cv2.imencode(".jpg", out, [int(cv2.IMWRITE_JPEG_QUALITY), quality])[1]
        out = cv2.imdecode(enc, cv2.IMREAD_COLOR)

    return out


def _to_yolo_label_lines(boxes: Sequence[CharBox], w: int, h: int) -> List[str]:
    lines: List[str] = []
    for b in boxes:
        x1 = max(0.0, min(float(w - 1), b.x1))
        y1 = max(0.0, min(float(h - 1), b.y1))
        x2 = max(0.0, min(float(w - 1), b.x2))
        y2 = max(0.0, min(float(h - 1), b.y2))
        bw = x2 - x1
        bh = y2 - y1
        if bw <= 1 or bh <= 1:
            continue

        cx = (x1 + x2) / 2.0 / w
        cy = (y1 + y2) / 2.0 / h
        nw = bw / w
        nh = bh / h
        lines.append(f"{b.cls_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
    return lines


def _make_sample(out_img: Path, out_lbl: Path, fonts: Sequence[Path], bg_dir: Path) -> None:
    w = random.randint(256, 1024)
    h = random.randint(128, 512)

    text = _make_dimension_text()
    text_rgba, boxes = _render_chars(text, w, h, fonts)

    # rotate text layer and bboxes around canvas center
    angle = random.uniform(-10.0, 10.0)
    pil_text = Image.fromarray(text_rgba, mode="RGBA")
    rot = pil_text.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
    rot_arr = np.array(rot)

    boxes = _transform_boxes_rotate(boxes, angle_deg=angle, cx=w / 2.0, cy=h / 2.0)

    bg = _background(h, w, bg_dir)
    alpha = rot_arr[:, :, 3:4].astype(np.float32) / 255.0
    fg = rot_arr[:, :, :3].astype(np.float32)
    merged = (fg * alpha + bg.astype(np.float32) * (1.0 - alpha)).astype(np.uint8)

    final = _augment(merged)

    label_lines = _to_yolo_label_lines(boxes, w=w, h=h)

    cv2.imwrite(str(out_img), final)
    out_lbl.write_text("\n".join(label_lines), encoding="utf-8")


def generate_dataset(out_dir: Path, n_train: int, n_val: int, seed: int = 1337) -> None:
    random.seed(seed)
    np.random.seed(seed)

    fonts = _find_fonts(Path("assets/fonts"))
    bg_dir = Path("assets/backgrounds")

    splits = [("train", n_train), ("val", n_val)]
    for split, n in splits:
        img_dir = out_dir / "images" / split
        lbl_dir = out_dir / "labels" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        for i in range(n):
            stem = f"dimchar_{split}_{i:06d}"
            _make_sample(
                out_img=img_dir / f"{stem}.jpg",
                out_lbl=lbl_dir / f"{stem}.txt",
                fonts=fonts,
                bg_dir=bg_dir,
            )
            if (i + 1) % 500 == 0:
                print(f"[{split}] {i + 1}/{n}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic character-level floor-plan dimensions dataset")
    parser.add_argument("--out", type=str, default="char_dimension_module/datasets/dim_chars")
    parser.add_argument("--train", type=int, default=20000)
    parser.add_argument("--val", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    generate_dataset(Path(args.out), n_train=args.train, n_val=args.val, seed=args.seed)
    print("Done.")
