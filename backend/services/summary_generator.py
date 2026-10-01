"""
AI-Powered Property Summary Generator

Generates a human-readable property description from structured pipeline output.
Uses template-based NLG with conditional logic -- no LLM required.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _get_area(room: Dict) -> float:
    area = room.get("area")
    if isinstance(area, dict) and area.get("value_sqft"):
        return float(area["value_sqft"])
    dp = room.get("dimensions_parsed") or {}
    if dp.get("area_sqft"):
        return float(dp["area_sqft"])
    if room.get("area_ft2"):
        return float(room["area_ft2"])
    return 0.0


def _round(value: float) -> int:
    """Round half up, matching Math.round in the frontend (Python's round()
    rounds half to even, and int() truncates)."""
    return int(value + 0.5)


def _get_label(room: Dict) -> str:
    return room.get("label") or room.get("label_raw") or room.get("name") or "Room"


def _get_dimensions(room: Dict) -> Optional[str]:
    return room.get("dimensions")


def _classify(label: str) -> str:
    low = label.lower()
    if "master" in low and "bed" in low:
        return "master_bedroom"
    if "bed" in low:
        return "bedroom"
    if "kitchen" in low:
        return "kitchen"
    if "hall" in low or "living" in low or "drawing" in low:
        return "living"
    if "dining" in low:
        return "dining"
    if "toilet" in low or "bath" in low or "wc" in low or "wash" in low:
        return "wet"
    if "balcony" in low or "terrace" in low or "sit" in low:
        return "outdoor"
    if "pooja" in low or "prayer" in low:
        return "pooja"
    if "store" in low or "utility" in low:
        return "utility"
    if "passage" in low or "lobby" in low or "corridor" in low:
        return "circulation"
    return "other"


def generate_summary(
    result_json: Dict[str, Any],
    page_index: Optional[int] = None,
) -> Dict[str, Any]:
    pages: List[Dict] = result_json.get("pages", [])

    if page_index is not None and 0 <= page_index < len(pages):
        all_rooms = pages[page_index].get("rooms", [])
    else:
        all_rooms = []
        for p in pages:
            all_rooms.extend(p.get("rooms", []))
        # Legacy format: rooms at top level
        if not all_rooms and "rooms" in result_json:
            legacy = result_json["rooms"]
            if isinstance(legacy, list):
                all_rooms = legacy

    if not all_rooms:
        return {"summary": "No rooms detected in this floor plan.", "highlights": []}

    # Classify rooms
    classified: Dict[str, List[Dict]] = {}
    for r in all_rooms:
        cat = _classify(_get_label(r))
        classified.setdefault(cat, []).append(r)

    bedrooms = classified.get("bedroom", [])
    master = classified.get("master_bedroom", [])
    all_beds = master + bedrooms
    kitchens = classified.get("kitchen", [])
    living = classified.get("living", [])
    dining = classified.get("dining", [])
    wet = classified.get("wet", [])
    outdoor = classified.get("outdoor", [])
    pooja = classified.get("pooja", [])
    utility = classified.get("utility", [])

    total_area = sum(_get_area(r) for r in all_rooms)
    total_rooms = len(all_rooms)

    # BHK classification
    bed_count = len(all_beds)
    hall_count = len(living) + len(dining)
    kitchen_count = len(kitchens)
    if bed_count == 0:
        bhk = "Studio"
    else:
        bhk = f"{bed_count}BHK"

    # Build sentences
    parts: List[str] = []

    # Opening
    area_str = f"approximately {_round(total_area)} sqft" if total_area > 0 else "area to be determined"
    parts.append(
        f"This is a {bhk} unit spanning {area_str}, "
        f"comprising {total_rooms} distinct spaces."
    )

    # Bedrooms
    if master:
        m = master[0]
        m_dim = _get_dimensions(m)
        m_area = _get_area(m)
        dim_str = f" ({m_dim})" if m_dim else ""
        area_str2 = f" at {_round(m_area)} sqft" if m_area > 0 else ""
        has_attached = any(
            _classify(_get_label(w)) == "wet"
            for w in all_rooms
        )
        attached = " with an attached bathroom" if has_attached and len(wet) > 0 else ""
        parts.append(
            f"The Master Bedroom{dim_str}{area_str2} is the primary sleeping area{attached}."
        )
    if len(bedrooms) == 1:
        b = bedrooms[0]
        dim = _get_dimensions(b)
        parts.append(f"There is 1 additional bedroom{' (' + dim + ')' if dim else ''}.")
    elif len(bedrooms) > 1:
        avg = sum(_get_area(b) for b in bedrooms) / len(bedrooms)
        parts.append(
            f"There are {len(bedrooms)} additional bedrooms"
            f"{f' averaging {_round(avg)} sqft each' if avg > 0 else ''}."
        )

    # Living / Kitchen
    if living and kitchens:
        parts.append("The living area connects to the kitchen, creating a social hub.")
    elif living:
        parts.append(f"The {_get_label(living[0])} serves as the main gathering space.")
    if kitchens:
        k = kitchens[0]
        k_dim = _get_dimensions(k)
        k_area = _get_area(k)
        if k_dim:
            parts.append(f"The kitchen measures {k_dim}{f' ({_round(k_area)} sqft)' if k_area else ''}.")

    # Wet areas
    if len(wet) > 0:
        parts.append(f"The unit has {len(wet)} wet area{'s' if len(wet) > 1 else ''} (toilet/bathroom).")

    # Outdoor
    if outdoor:
        labels = [_get_label(o) for o in outdoor]
        parts.append(f"Outdoor spaces include: {', '.join(labels)}.")

    # Special rooms
    if pooja:
        parts.append("A dedicated Pooja/prayer room is provided.")
    if utility:
        parts.append(f"Utility/storage space is available ({len(utility)} room{'s' if len(utility) > 1 else ''}).")

    # Highlights
    highlights: List[str] = []
    highlights.append(f"{bhk} configuration with {total_rooms} spaces")
    if total_area > 0:
        highlights.append(f"Total carpet area: {_round(total_area)} sqft")
    if master:
        highlights.append("Dedicated Master Bedroom")
    if len(wet) >= len(all_beds) and len(all_beds) > 0:
        highlights.append("All bedrooms have attached bathrooms")
    if len(outdoor) >= 2:
        highlights.append(f"{len(outdoor)} outdoor spaces for cross-ventilation")
    elif len(outdoor) == 1:
        highlights.append(f"1 outdoor space ({_get_label(outdoor[0])})")
    if pooja:
        highlights.append("Vastu-friendly Pooja room")
    if dining:
        highlights.append("Separate dining area")

    # Area distribution insight
    if total_area > 0:
        bed_area = sum(_get_area(r) for r in all_beds)
        living_area = sum(_get_area(r) for r in living + dining)
        bed_pct = _round((bed_area / total_area) * 100) if bed_area else 0
        living_pct = _round((living_area / total_area) * 100) if living_area else 0
        if bed_pct > 0:
            highlights.append(f"{bed_pct}% of area allocated to bedrooms")
        if living_pct > 0:
            highlights.append(f"{living_pct}% of area allocated to living/dining")

    summary_text = " ".join(parts)

    return {
        "summary": summary_text,
        "highlights": highlights,
        "bhk": bhk,
        "total_area_sqft": _round(total_area) if total_area > 0 else None,
        "room_count": total_rooms,
        "bedroom_count": len(all_beds),
        "bathroom_count": len(wet),
        "outdoor_count": len(outdoor),
    }
