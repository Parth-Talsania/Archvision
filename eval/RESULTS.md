# End-to-end evaluation

10 floor plans (72 rooms) that the model never saw during training or validation.
Ground truth: room labels and dimensions as printed on each plan (`eval/ground_truth.txt`).
Reproduce with `python eval/evaluate.py`.

Note: one dimension-parser fix (OCR reading a dash as a dot, and a missing space after
"x") was made after seeing plan E-22 fail in this evaluation, so these plans are not
fully untouched test data. Without that fix, exact dimensions were 53/67 instead of 54/68.

| Metric | Result |
|---|---|
| Rooms found (recall) | 69/72 (96%) |
| Detections that are real rooms (precision) | 69/75 (92%) |
| Correct label, of rooms found | 68/69 (99%) |
| Dimensions exact (within ½"), of rooms found | 54/68 (79%) |
| Dimensions within 3", of rooms found | 55/68 (81%) |
| Median area error, where area was computed | 0.4% (mean 20.8%, n=62) |

## Per plan

| Plan | Rooms | Detections | Found | Label correct | Dims exact |
|---|---|---|---|---|---|
| E-06.png | 6 | 7 | 6 | 6/6 | 6/6 |
| E-17.png | 7 | 7 | 7 | 6/7 | 6/7 |
| E-22.png | 8 | 8 | 8 | 8/8 | 8/8 |
| E-26.png | 10 | 10 | 9 | 9/9 | 8/8 |
| N2.png | 8 | 8 | 8 | 8/8 | 1/8 |
| N9.png | 4 | 4 | 4 | 4/4 | 4/4 |
| N18.PNG | 6 | 6 | 6 | 6/6 | 5/6 |
| S15.PNG | 10 | 10 | 8 | 8/8 | 3/8 |
| W4.png | 5 | 5 | 5 | 5/5 | 5/5 |
| W8.png | 8 | 10 | 8 | 8/8 | 8/8 |

## Misses and errors

| Plan | Ground truth | Prediction | Problem |
|---|---|---|---|
| E-17.png | Toilet · 7'-0" x 4'-0" | Toilet · - | no dimensions |
| E-17.png | HALL & Dining · 18'-6" x 13'-1 1/2" | Dining · 18'6" x 13'1" | label |
| E-26.png | HALL · 16'-11" x 20'-8 1/2" | – | not found |
| N2.png | Toilet · 4'-0" x 6'-10 1/2" | Toilet · 4'1" x 6'10" | dims off by 1.0" |
| N2.png | Master Bed Room · 11'-4 1/2" x 11'-8 1/2" | Master Bed Room · 14'0" x 11'8" | dims off by 27.5" |
| N2.png | HALL · 14'-4 1/2" x 14'-1" | Hall · 14'4" x 4'0" | dims off by 121.0" |
| N2.png | Bed Room · 11'-4 1/2" x 10'-0" | Bed Room · - | no dimensions |
| N2.png | Bed Room · 11'-4 1/2" x 10'-0" | Bed Room · - | no dimensions |
| N2.png | Toilet · 4'-0" x 6'-0" | Toilet · - | no dimensions |
| N2.png | Sit Out · 10'-9" x 6'-3 1/2" | Sit Out · 9'0" x 6'0" | dims off by 21.0" |
| N18.PNG | Toilet · 11'-4 1/2" x 4'-0" | Toilet · 11'4" x 44'0" | dims off by 391.5" |
| S15.PNG | Toilet · 4'-0" x 6'-0" | Toilet · - | no dimensions |
| S15.PNG | Bed Room · 10'-0" x 10'-0" | Bed Room · 4'7" x 2'9" | dims off by 87.0" |
| S15.PNG | Pooja · 4'-0" x 3'-7 1/2" | – | not found |
| S15.PNG | Bed Room · m: 3.47 x 3.29 | Bed Room · 10'4" x 10'0" | dims off by 12.6" |
| S15.PNG | Master Bed Room · 11'-4 1/2" x 10'-4 1/2" | Master Bed Room · 11'4" x 4'4" | dims off by 72.5" |
| S15.PNG | Toilet · 4'-0" x 7'-0" | Toilet · - | no dimensions |
| S15.PNG | Sit-Out · 10'-4 1/2" x 7'-4 1/2" | – | not found |
