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


def _fmt(text):
    r = parse_dimensions(text)
    return r.formatted if r else None


def test_feet_only_values_are_not_split_into_feet_and_inches():
    # Previously "12'" was read as 1'2".
    assert _fmt("12-0' x 12'") == "12'0\" x 12'0\""
    assert _fmt("10'-0\"x13'-") == "10'0\" x 13'0\""
    assert _fmt("12'5' x10'\"") == "12'5\" x 10'0\""
    assert _fmt("6'0 x4'") == "6'0\" x 4'0\""


def test_ocr_noise_still_parses_as_before():
    assert _fmt("7'-72\" x 10'-6\"") == "7'7\" x 10'6\""      # ghost '2' from ½
    assert _fmt("10'-7z x 8'") == "10'7\" x 8'0\""            # ghost 'z' from ½
    assert _fmt("14'-10-1/2\" x 7'-1-1/2\"") == "14'10\" x 7'1\""
    assert _fmt("106 x 103") == "10'6\" x 10'3\""             # glued feet+inches
    assert _fmt("13'-62 10'-0'") == "13'6\" x 10'0\""
    assert _fmt("18'0 12'0\"") == "18'0\" x 12'0\""
    assert _fmt("4'0\" X3'-8'") == "4'0\" x 3'8\""            # inch mark read as '


def test_door_tags_are_not_read_as_dimensions():
    assert _fmt("Toilet\n4'-\"\nX\n750\"\nD2") is None


def test_ocr_dot_and_missing_x_spacing():
    # Real OCR line from plan E-22 (14'-4 1/2" x 25'-11"): dash read as a dot
    # and no space after the "x".
    assert _fmt("14'.41\" x25-11\"") == "14'4\" x 25'11\""
    assert _fmt("12'-0\"x10'-6\"") == "12'0\" x 10'6\""
    # A digit right after a foot mark is inches, never a standalone feet value.
    assert _fmt("1i'4x9-7k\"") != "4'0\" x 9'7\""
