from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

from .config import ParseConfig
from .types import AreaParseResult, DimensionParseResult, OCRToken

_SQFT_PER_SQM = 10.7639

# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    s = text or ""
    # Strip Unicode fraction characters entirely -- EasyOCR can't read them
    # reliably and they just add noise.  Dropping ½ from 10'-7½" gives 10'-7"
    # which is close enough (off by 0.5 inch) and avoids catastrophic misparsing.
    for ch in "\u00bd\u00bc\u00be\u2153\u2154":  # ½ ¼ ¾ ⅓ ⅔
        s = s.replace(ch, "")
    # Normalize quote variants
    s = s.replace("\u2018", "'").replace("\u2019", "'").replace("`", "'").replace("\u2032", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2033", '"')
    s = s.replace("\u00d7", "x").replace("*", "x")
    # Strip fraction-ghost characters left by EasyOCR misreading superscript ½.
    # EasyOCR turns ½ into trailing '2', 'z', ']', or '}' glued to the inch digit.
    # Pattern: a digit followed by [2z]} right before a quote, 'x', or end of string.
    # The lookaheads don't consume the space before "x", which the
    # width/height split in parse_dimensions_candidates relies on.
    s = re.sub(r'(\d)[z\]})](?=\s*["\u2033]|\s*$|\s*[xX]\s)', r'\1', s)
    # Handle the '2' ghost: an inch digit + '2' before an inch mark or "x",
    # e.g. 7'-72" -> 7'-7". Only applies to inches (after a foot mark or a
    # feet-dash), so a feet value like the "12" in "12 x 10" is left alone.
    s = re.sub(r"((?:['\u2032]|\d\s*-)\s*-?\s*)(\d)2(?=\s*[\"\u2033]|\s*[xX]\s)", _strip_ghost_2, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _strip_ghost_2(m: re.Match) -> str:
    """Callback for ghost-2 regex. Only strip the trailing '2' if the
    two-digit inch value would be >= 12 (impossible real inch value)."""
    prefix, digit = m.group(1), m.group(2)
    if int(digit + "2") >= 12:
        return prefix + digit  # strip the ghost '2'
    return m.group(0)  # keep as-is (e.g. '02' is a valid 2 inches)


# ---------------------------------------------------------------------------
# Dimension parsing -- complete rewrite.
#
# Indian floor plan format:  N'-N"  x  N'-N"   (with optional fractions)
# Examples:  11'-9" x 10'-3"    14'-10-1/2" x 7'-1-1/2"   10'6" x 8'0"
#
# Strategy: find all "measurement" tokens (feet-inch patterns), then pair
# them across an "x" separator.  Fallback: pair the first two measurements.
# ---------------------------------------------------------------------------

# Feet-and-inches measurement: captures feet, inches, and optional fraction.
_FEET_INCH = (
    r"(?P<ft>\d{1,2})"
    r"\s*['\u2032`\u2018\u2019]?\s*"  # optional apostrophe
    r"[-\s]*"                         # separator (dash, space, or nothing)
    r"(?P<inch>\d{1,2})"
    r"(?:\s*[-\s]*(?P<fn>\d)\s*/\s*(?P<fd>\d))?"  # optional fraction  N/D
    r'\s*["\u2033\u201c\u201d]?'      # optional double-quote
)
# Feet only: a foot mark with no inch digits after it, e.g. the 12' in
# "12' x 10'6"". Without this, the pattern above splits "12'" into 1'2".
# Limited to 1-30 ft: OCR often drops the inch mark, so a bigger value such
# as "44'" is more likely 4'4" and is left to _FEET_INCH.
_FEET_MARK_ONLY = r"(?<!\d)(?P<ft_only>30|[12]\d|[1-9])\s*['\u2032`\u2018\u2019](?!\s*-?\s*\d)"
# Bare feet: a plain 1-30 number with no marks, like "12" in "12 x 10".
# Not part of a word or decimal (e.g. the 2 in door tag "D2") and not
# followed by inch digits (so "10 6" stays 10'6").
_BARE_FEET = r"(?<![\w.,])(?P<ft_bare>30|[12]\d|[1-9])(?![\w.,/'\"\u2032\u2033\u201c\u201d`\u2018\u2019]|\s*-?\s*\d)"

_MEASURE_RE = re.compile(_FEET_MARK_ONLY + "|" + _FEET_INCH)
_MEASURE_BARE_RE = re.compile(_FEET_MARK_ONLY + "|" + _BARE_FEET + "|" + _FEET_INCH)


def _parse_measure(text: str, allow_bare: bool = False) -> List[Tuple[int, int, int, int, int, int]]:
    """Extract all (feet, inches, frac_num, frac_den, start, end) from text.

    ``allow_bare`` also accepts plain numbers such as the "12" in "12 x 10" as
    feet. It is only used beside an explicit "x", because elsewhere stray
    numbers (e.g. "Bedroom 2") would be mistaken for measurements.
    """
    results = []
    pattern = _MEASURE_BARE_RE if allow_bare else _MEASURE_RE
    for m in pattern.finditer(text):
        groups = m.groupdict()
        if groups["ft_only"] is not None:
            ft, inch, fnum_s, fden_s = int(groups["ft_only"]), 0, None, None
        elif groups.get("ft_bare") is not None:
            ft, inch, fnum_s, fden_s = int(groups["ft_bare"]), 0, None, None
        else:
            ft, inch = int(groups["ft"]), int(groups["inch"])
            fnum_s, fden_s = groups["fn"], groups["fd"]
        fnum = int(fnum_s) if fnum_s else 0
        fden = int(fden_s) if fden_s else 1
        if fden == 0:
            fden = 1
        # Ignore fractions -- just use whole inches for reliability.
        # A ½ inch difference is negligible for floor plan analysis.
        if inch >= 12:
            # Two-digit inch >= 12 is almost certainly a fraction ghost
            # (e.g. OCR read "72" for "7½").  Take just the first digit.
            inch = inch // 10
        if ft < 1 or ft > 50:
            continue
        if inch > 11:
            inch = 0
        results.append((ft, inch, fnum, fden, m.start(), m.end()))
    return results


def _build_dim(ft1: int, in1: int, ft2: int, in2: int,
               raw: str, conf: float) -> DimensionParseResult:
    w_total = ft1 + in1 / 12.0
    h_total = ft2 + in2 / 12.0
    formatted = f"{ft1}'{in1}\" x {ft2}'{in2}\""
    return DimensionParseResult(
        raw=raw, w_ft=ft1, w_in=in1, h_ft=ft2, h_in=in2,
        w_total_ft=round(w_total, 4), h_total_ft=round(h_total, 4),
        formatted=formatted, confidence=conf,
    )


def parse_dimensions(text: str, conf: float = 0.0) -> Optional[DimensionParseResult]:
    candidates = parse_dimensions_candidates(text, conf=conf)
    return candidates[0] if candidates else None


def parse_dimensions_candidates(text: str, conf: float = 0.0) -> List[DimensionParseResult]:
    norm = normalize_text(text)
    results: List[DimensionParseResult] = []

    # Strategy 1: Split on 'x' separator and parse each side
    if re.search(r"\s[xX]\s", norm):
        parts = re.split(r"\s[xX]\s", norm, maxsplit=1)
        if len(parts) == 2:
            left_m = _parse_measure(parts[0], allow_bare=True)
            right_m = _parse_measure(parts[1], allow_bare=True)
            if left_m and right_m:
                lft, lin = left_m[-1][0], left_m[-1][1]  # last match (closest to x)
                rft, rin = right_m[0][0], right_m[0][1]  # first match (closest to x)
                results.append(_build_dim(lft, lin, rft, rin, text, conf))

    # Strategy 2: Find all measurements and pair them
    if not results:
        measures = _parse_measure(norm)
        if len(measures) >= 2:
            ft1, in1 = measures[0][0], measures[0][1]
            ft2, in2 = measures[1][0], measures[1][1]
            results.append(_build_dim(ft1, in1, ft2, in2, text, conf))

    # Strategy 3: OCR sometimes gives "106 x 103" for 10'6" x 10'3"
    if not results:
        m = re.search(r"(\d{2,3})\s*[xX]\s*(\d{2,3})", norm)
        if m:
            a, b = m.group(1), m.group(2)
            ft1, in1 = _split_compact(a)
            ft2, in2 = _split_compact(b)
            if ft1 and ft2:
                results.append(_build_dim(ft1, in1, ft2, in2, text, conf * 0.7))

    # Deduplicate
    seen = set()
    out = []
    for r in results:
        key = (r.w_ft, r.w_in, r.h_ft, r.h_in)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _split_compact(digits: str) -> Tuple[Optional[int], int]:
    """Split '106' -> (10, 6) or '83' -> (8, 3)."""
    if len(digits) == 3:
        ft, inch = int(digits[:2]), int(digits[2])
        if 2 <= ft <= 40 and 0 <= inch <= 11:
            return ft, inch
    if len(digits) == 2:
        ft, inch = int(digits[0]), int(digits[1])
        if 2 <= ft <= 40 and 0 <= inch <= 11:
            return ft, inch
    return None, 0


# ---------------------------------------------------------------------------
# Area parsing
# ---------------------------------------------------------------------------

def parse_area(text: str) -> Optional[AreaParseResult]:
    norm = normalize_text(text).lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(sq\.?\s*ft|sqft|ft2|ft\^2|sq\.?\s*m|sqm|m2|m\^2)", norm)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).replace(" ", "")
    sqft = val * _SQFT_PER_SQM if ("m" in unit and "ft" not in unit) else val
    return AreaParseResult(raw=text, value=val, unit=unit, sqft=round(sqft, 4))


# ---------------------------------------------------------------------------
# Label picking -- rewrite with fuzzy matching
# ---------------------------------------------------------------------------

_KNOWN_LABELS = [
    "Master Bedroom", "Master Bed Room", "Bed Room", "Bedroom",
    "Kitchen", "Kitchen / Dining", "Kitchen/Dining",
    "Hall", "Living", "Living Room", "Drawing Room",
    "Toilet", "Bathroom", "WC",
    "Pooja", "Puja", "Prayer",
    "Sit-Out", "Sit Out", "Balcony",
    "Dining", "Store", "Stair",
]


def _edit_distance(a: str, b: str) -> int:
    """Simple Levenshtein distance."""
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(la):
        curr = [i + 1] + [0] * lb
        for j in range(lb):
            cost = 0 if a[i] == b[j] else 1
            curr[j + 1] = min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost)
        prev = curr
    return prev[lb]


def _fuzzy_match_label(text: str, synonyms: dict, threshold: float = 0.35) -> Optional[str]:
    """Try exact synonym lookup first, then fuzzy match against known labels."""
    clean = text.strip()
    # Strip leading/trailing non-alpha (OCR artifacts)
    clean = re.sub(r'^[^A-Za-z]+', '', clean)
    clean = re.sub(r'[^A-Za-z\s/\-]+$', '', clean)
    if not clean:
        return None

    key = clean.lower()

    # Exact synonym match
    if key in synonyms:
        return synonyms[key]

    # Exact match against known labels
    for lbl in _KNOWN_LABELS:
        if key == lbl.lower():
            return lbl

    # Fuzzy match: find closest known label or synonym value
    best_label = None
    best_ratio = 1.0  # lower is better (normalized edit distance)
    candidates = list(synonyms.items()) + [(lbl.lower(), lbl) for lbl in _KNOWN_LABELS]
    for candidate_key, candidate_val in candidates:
        dist = _edit_distance(key, candidate_key)
        max_len = max(len(key), len(candidate_key))
        if max_len == 0:
            continue
        ratio = dist / max_len
        if ratio < best_ratio:
            best_ratio = ratio
            best_label = candidate_val
    if best_ratio <= threshold:
        return best_label
    return None


def pick_label(lines: List[str], line_tokens: List[List[OCRToken]],
               cfg: ParseConfig) -> Tuple[Optional[str], float]:
    """Pick best room label. Checks both merged lines AND individual tokens,
    preferring anything that fuzzy-matches a known room type.
    """
    candidates: List[Tuple[str, Optional[str], float, float]] = []

    def _is_dim_text(txt: str) -> bool:
        if re.search(r"\d", txt) and re.search(r"['\"\-]\s*\d", txt):
            return True
        if re.search(r"\d\s*[xX]\s*\d", txt):
            return True
        return False

    # Check merged lines
    for line, tokens in zip(lines, line_tokens):
        txt = normalize_text(line)
        if not txt or _is_dim_text(txt):
            continue
        alpha = len(re.findall(r"[A-Za-z]", txt))
        if alpha < 2:
            continue
        conf = float(sum(t.conf for t in tokens) / max(1, len(tokens)))
        matched = _fuzzy_match_label(txt, cfg.label_synonyms)
        score = alpha + min(20, len(txt))
        if matched:
            score += 50
        candidates.append((txt, matched, conf, score))

    # Also check individual tokens (catches cases where line merging
    # glues good text with garbage from adjacent rooms)
    all_tokens = [t for grp in line_tokens for t in grp]
    for tok in all_tokens:
        txt = normalize_text(tok.text)
        if not txt or _is_dim_text(txt):
            continue
        alpha = len(re.findall(r"[A-Za-z]", txt))
        if alpha < 2:
            continue
        matched = _fuzzy_match_label(txt, cfg.label_synonyms)
        if matched:
            score = alpha + min(20, len(txt)) + 50
            candidates.append((txt, matched, tok.conf, score))

    if not candidates:
        return None, 0.0

    candidates.sort(key=lambda c: (c[3], c[2]), reverse=True)
    raw, matched, conf, _ = candidates[0]
    return (matched or raw), conf


# ---------------------------------------------------------------------------
# Dimension selection (for a room)
# ---------------------------------------------------------------------------

def best_dimension(lines: Iterable[str], line_tokens: List[List[OCRToken]],
                   cfg: ParseConfig) -> Optional[DimensionParseResult]:
    best: Optional[DimensionParseResult] = None
    for idx, line in enumerate(lines):
        conf = 0.0
        if idx < len(line_tokens) and line_tokens[idx]:
            conf = float(sum(t.conf for t in line_tokens[idx]) / len(line_tokens[idx]))
        parsed = parse_dimensions(line, conf=conf)
        if parsed is None:
            continue
        if parsed.confidence < cfg.min_dim_conf:
            continue
        if best is None or parsed.confidence > best.confidence:
            best = parsed
    return best


# ---------------------------------------------------------------------------
# Conversion helpers (kept for backward compatibility)
# ---------------------------------------------------------------------------

def to_total_inches(ft: int, inch: float) -> float:
    return (ft * 12) + inch

def to_total_feet(ft: int, inch: float) -> float:
    return ft + (inch / 12.0)

def inches_to_feet_inches(total_inches: float) -> tuple:
    ft = int(total_inches // 12)
    inch = total_inches % 12
    return ft, round(inch, 2)
