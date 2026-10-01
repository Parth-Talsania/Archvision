from pipeline.parse_semantics import normalize_text, parse_dimensions


def test_normalize_quotes_and_x():
    s = '12’-0” × 10’-6”'
    assert normalize_text(s) == '12\'-0" x 10\'-6"'


def test_parse_dimension_formats():
    a = parse_dimensions("12'-0\" x 10'-6\"")
    assert a is not None
    assert a.w_ft == 12 and a.w_in == 0 and a.h_ft == 10 and a.h_in == 6

    b = parse_dimensions("12' x 10'6\"")
    assert b is not None
    assert b.w_ft == 12 and b.h_ft == 10 and b.h_in == 6

    c = parse_dimensions("12 x 10")
    assert c is not None
    assert c.w_ft == 12 and c.h_ft == 10

    d = parse_dimensions("9-6\" 10-7\"")
    assert d is not None
    assert d.w_ft == 9 and d.w_in == 6
