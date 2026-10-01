from backend.services.summary_generator import generate_summary
from pipeline.frontend_schema import has_room_label


def test_has_room_label_counts_real_labels_only():
    # A label equal to the YOLO class name (e.g. "Hall") is still a label.
    assert has_room_label("Hall")
    assert has_room_label("Master Bedroom")
    assert not has_room_label("room")
    assert not has_room_label("Room ")
    assert not has_room_label("")
    assert not has_room_label(None)


def _room(label, sqft):
    return {"label": label, "area": {"value_sqft": sqft}}


def test_summary_rounds_area_like_the_frontend():
    # 400.5 + 328.4 = 728.9 sqft: the dashboard shows Math.round -> 729,
    # so the summary must not truncate to 728.
    result = {"pages": [{"rooms": [_room("Living", 400.5), _room("Bedroom", 328.4)]}]}
    summary = generate_summary(result)
    assert summary["total_area_sqft"] == 729
    assert "729 sqft" in summary["summary"]
