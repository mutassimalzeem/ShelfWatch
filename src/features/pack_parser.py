"""Pack-size parsing: normalize "500 gm", "1 ltr", "12 pack" etc. from titles.

Used to derive per-unit prices (price / base quantity) so different pack
sizes of the same product become comparable across retailers.
"""
import re

UNIT_ALIASES = {
    "gm": ("gm", 1.0), "g": ("gm", 1.0), "gram": ("gm", 1.0), "grams": ("gm", 1.0),
    "kg": ("gm", 1000.0), "kilo": ("gm", 1000.0), "kilogram": ("gm", 1000.0),
    "ml": ("ml", 1.0), "milliliter": ("ml", 1.0), "millilitre": ("ml", 1.0),
    "ltr": ("ml", 1000.0), "litre": ("ml", 1000.0), "liter": ("ml", 1000.0),
    "l": ("ml", 1000.0),
    "pc": ("pcs", 1.0), "pcs": ("pcs", 1.0), "piece": ("pcs", 1.0),
    "pieces": ("pcs", 1.0), "pack": ("pack", 1.0), "packs": ("pack", 1.0),
    "dozen": ("pcs", 12.0), "dz": ("pcs", 12.0),
}

_PATTERN = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>grams?|gm|g|kilo(?:gram)?|kg|millilitre|"
    r"milliliter|ml|ltr|litre|liter|l|pieces?|pcs?|packs?|dozen|dz)\b", re.I)


def parse_pack(title):
    """Return pack info for a product title.

    Keys: pack_raw (matched text), pack_qty, pack_unit (gm|ml|pcs|pack),
    base_qty (quantity expressed in gm / ml / pcs / pack so unit prices are
    comparable). All None when nothing parsable is present.
    Note: the FIRST match wins, e.g. "8 pcs 496 gm" reports the piece count.
    """
    empty = {"pack_raw": None, "pack_qty": None,
             "pack_unit": None, "base_qty": None}
    if not title:
        return empty
    m = _PATTERN.search(str(title))
    if not m:
        return empty
    qty = float(m.group("qty"))
    unit, factor = UNIT_ALIASES[m.group("unit").lower()]
    return {"pack_raw": m.group(0).strip(), "pack_qty": qty,
            "pack_unit": unit, "base_qty": round(qty * factor, 3)}


def unit_price(price, title):
    """Price per base unit (BDT per gm/ml/pc/pack); None when not computable."""
    pack = parse_pack(title)
    if not pack["base_qty"] or not price:
        return None
    return round(float(price) / pack["base_qty"], 6)

