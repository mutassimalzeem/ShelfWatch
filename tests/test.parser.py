from src.features.pack_parser import parse_pack_size, calculate_normalized_price

def test_parse_pack_size_grams():
    val, unit, norm = parse_pack_size("Oreo Biscuit 120 gm")
    assert val == 120.0
    assert unit == "g"
    assert norm == 120.0

def test_parse_pack_size_kilograms():
    val, unit, norm = parse_pack_size("Rice 1.5 kg")
    assert val == 1.5
    assert unit == "kg"
    assert norm == 1500.0

def test_calculate_normalized_price():
    assert calculate_normalized_price(100.0, 1000.0) == 0.1
    assert calculate_normalized_price(50.0, 500.0) == 0.1
    