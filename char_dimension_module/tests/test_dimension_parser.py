from char_dimension_module.dimension_char_reader import normalize_dimension_text, parse_dimension_candidate


def _must_parse(text: str):
    parsed = parse_dimension_candidate(text, char_conf=0.95)
    assert parsed is not None, f"Failed to parse: {text}"
    return parsed


def test_parse_12_0_quote():
    p = _must_parse("12'-0\"")
    assert p.canonical_text.startswith("12'-0\"")
    assert abs(p.side_a_inches - 144.0) < 1e-6


def test_parse_12_0_no_dash():
    p = _must_parse("12'0\"")
    assert p.canonical_text.startswith("12'-0\"")


def test_parse_fraction():
    p = _must_parse("12'-6 1/2\"")
    assert abs(p.side_a_inches - 150.5) < 1e-6


def test_parse_pair():
    p = _must_parse("10'-0\" x 8'-0\"")
    assert p.side_b_inches is not None
    assert abs(p.side_a_inches - 120.0) < 1e-6
    assert abs(p.side_b_inches - 96.0) < 1e-6


def test_parse_pair_with_spaces():
    p = _must_parse("10' - 0\" x 8' - 0\"")
    assert p.side_b_inches is not None
    assert p.area_sqft is not None


def test_parse_unicode_fraction():
    p = _must_parse("10'-6\u00bd\" x 9'-3\"")
    assert p.side_b_inches is not None


def test_normalize_canonical_zero_inches():
    assert normalize_dimension_text("12' 0\"") == "12'-0\""
