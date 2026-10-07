import re
from typing import Tuple, Optional

def parse_pack_size(title: str) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    """
    Extracts numerical quantity, unit, and converts to grams/ml.
    Returns: (raw_value, unit, normalized_grams_or_ml)
    """

    if not isinstance(title, str):
        return None, None, None

    # Patterns for: 500gm, 1kg, 250 gm, 1.5 ltr, 200 ml, ± 50 gm
    kg_pattern = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilo)', title, re.IGNORECASE)
    if kg_pattern:
        val = float(kg_pattern.group(1))
        return val, 'kg', val * 1000.0

    gm_pattern = re.search(r'(?:±\s*)?(\d+(?:\.\d+)?)\s*(?:gm|g|grams|gram)\b', title, re.IGNORECASE)
    if gm_pattern:
        val = float(gm_pattern.group(1))
        return val, 'g', val

    litre_pattern = re.search(r'(\d+(?:\.\d+)?)\s*(?:l|ltr|litre|liter)\b', title, re.IGNORECASE)
    if litre_pattern:
        val = float(litre_pattern.group(1))
        return val, 'l', val * 1000.0

    ml_pattern = re.search(r'(\d+(?:\.\d+)?)\s*(?:ml|milli)\b', title, re.IGNORECASE)
    if ml_pattern:
        val = float(ml_pattern.group(1))
        return val, 'ml', val

    each_pattern = re.search(r'\b(?:each|pc|pcs|piece)\b', title, re.IGNORECASE)
    if each_pattern:
        return 1.0, 'piece', None

    return None, None, None

def calculate_normalized_price(price: float, normalized_units: Optional[float]) -> Optional[float]:
    """Calculates Price per 100g or 100ml"""
    if price and normalized_units and normalized_units > 0:
        return round((price / normalized_units) * 100.0, 2)
    return None