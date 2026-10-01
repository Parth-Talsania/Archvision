# Integration Notes (No Existing File Modified)

If you want to wire this into your existing `floor_plan_pipeline.py`, add this in your room loop after room polygons are available:

```python
from char_dimension_module.dimension_char_reader import extract_room_dimensions

res = extract_room_dimensions(
    image=image,
    room_polygon=room_polygon,
    model_path="weights/dim_char_yolov8n.pt",
    device="cuda",
    debug=True,
    debug_path=f"debug/room_{room_id:03d}_chars.png",
)

room["dimensions"] = res.dimensions_text
room["dimension_source"] = "char_detector"
room["dimension_confidence"] = float(res.confidence)
room["dimensions_parsed"] = None
if res.parsed is not None:
    room["dimensions_parsed"] = {
        "a_inches": res.parsed.side_a_inches,
        "b_inches": res.parsed.side_b_inches,
        "area_sqft": res.parsed.area_sqft,
        "canonical": res.parsed.canonical_text,
    }
```

This keeps OCR for labels only and uses char detector for dimensions.
