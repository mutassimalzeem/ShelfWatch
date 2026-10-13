import re
from typing import Optional, Tuple


def parse_pack_size_details(title: str) -> dict:
    """Extract a pack size and return normalized metadata for downstream logic."""
    if not isinstance(title, str):
        return {
            "raw_value": None,
            "unit": None,
            "normalized_amount": None,
            "normalized_unit": None,
            "parse_status": "missing",
        }

    text = title.strip()
    if not text:
        return {
            "raw_value": None,
            "unit": None,
            "normalized_amount": None,
            "normalized_unit": None,
            "parse_status": "missing",
        }

    multi_match = re.search(
        r"(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*(kg|kgs|kilo|kilogram|g|gm|grams|gram|l|ltr|litre|liter|ml|pcs?|pieces?|packs?)\b",
        text,
        re.IGNORECASE,
    )
    if multi_match:
        multiplier = float(multi_match.group(1))
        amount = float(multi_match.group(2))
        unit_token = multi_match.group(3).lower()
        total = multiplier * amount
        unit = _normalize_unit_token(unit_token)
        normalized = _normalize_amount(total, unit)
        return {
            "raw_value": total,
            "unit": unit,
            "normalized_amount": normalized,
            "normalized_unit": unit,
            "parse_status": "parsed",
        }

    pack_match = re.search(
        r"pack(?:\s+of)?\s+(\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if pack_match:
        value = float(pack_match.group(1))
        return {
            "raw_value": value,
            "unit": "piece",
            "normalized_amount": None,
            "normalized_unit": None,
            "parse_status": "parsed",
        }

    weight_pattern = re.search(
        r"(?:±\s*)?(\d+(?:\.\d+)?)\s*(kg|kgs|kilo|kilogram|g|gm|grams|gram)\b",
        text,
        re.IGNORECASE,
    )
    if weight_pattern:
        value = float(weight_pattern.group(1))
        unit = _normalize_unit_token(weight_pattern.group(2))
        return {
            "raw_value": value,
            "unit": unit,
            "normalized_amount": _normalize_amount(value, unit),
            "normalized_unit": unit,
            "parse_status": "parsed",
        }

    volume_pattern = re.search(
        r"(?:±\s*)?(\d+(?:\.\d+)?)\s*(l|ltr|litre|liter|ml)\b",
        text,
        re.IGNORECASE,
    )
    if volume_pattern:
        value = float(volume_pattern.group(1))
        unit = _normalize_unit_token(volume_pattern.group(2))
        return {
            "raw_value": value,
            "unit": unit,
            "normalized_amount": _normalize_amount(value, unit),
            "normalized_unit": unit,
            "parse_status": "parsed",
        }

    if re.search(r"\b(?:each|pc|pcs|piece|pieces)\b", text, re.IGNORECASE):
        return {
            "raw_value": 1.0,
            "unit": "piece",
            "normalized_amount": None,
            "normalized_unit": None,
            "parse_status": "parsed",
        }

    return {
        "raw_value": None,
        "unit": None,
        "normalized_amount": None,
        "normalized_unit": None,
        "parse_status": "ambiguous",
    }


def _normalize_unit_token(unit_token: str) -> str:
    token = unit_token.lower().strip()
    if token in {"kg", "kgs", "kilo", "kilogram", "kilograms"}:
        return "kg"
    if token in {"g", "gm", "grams", "gram", "gms"}:
        return "g"
    if token in {"l", "ltr", "ltrs", "litre", "litres", "liter", "liters"}:
        return "l"
    if token in {"ml", "milliliter", "millilitre", "milliliters", "millilitres"}:
        return "ml"
    if token in {"pcs", "pc", "piece", "pieces", "pack", "packs"}:
        return "piece"
    return token


def _normalize_amount(value: float, unit: Optional[str]) -> Optional[float]:
    if value is None or unit is None:
        return None
    if unit == "kg":
        return value * 1000.0
    if unit == "l":
        return value * 1000.0
    return value


def parse_pack_size(title: str) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    """Backward-compatible API returning (raw_value, unit, normalized_amount)."""
    details = parse_pack_size_details(title)
    return details["raw_value"], details["unit"], details["normalized_amount"]


def calculate_normalized_price(price: float, normalized_units: Optional[float]) -> Optional[float]:
    """Calculate price per 100g or 100ml."""
    if price and normalized_units and normalized_units > 0:
        return round((price / normalized_units) * 100.0, 2)
    return None


def calculate_price_per_unit(price: float, quantity: Optional[float], unit: Optional[str]) -> Optional[float]:
    """Calculate price per single unit when the quantity is known and meaningful."""
    if not price or quantity is None or quantity <= 0:
        return None
    if unit in {"piece", "pack"}:
        return round(price / quantity, 2)
    if unit in {"g", "kg", "ml", "l"}:
        return round(price / quantity, 2)
    return None