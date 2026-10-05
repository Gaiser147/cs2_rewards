import math
import re


def format_eur(cents: int) -> str:
    return f"{cents // 100},{cents % 100:02d} €"


def eur_to_cents_ceil(value: float) -> int:
    # Aufrunden, damit nie ein Preis zu niedrig gegen ein Limit geprüft wird.
    return math.ceil(round(value * 100, 6))


_PRICE_RE = re.compile(r"^\s*(\d+)(?:[.,](\d{1,2}))?\s*(?:€|eur)?\s*$", re.IGNORECASE)


def parse_eur(text: str) -> int:
    """'1,84', '1.84', '1,84 €', '2' -> Cent. ValueError bei allem anderen."""
    m = _PRICE_RE.match(text)
    if not m:
        raise ValueError(f"Kein gültiger Euro-Betrag: {text!r}")
    euros, cents = m.group(1), (m.group(2) or "0").ljust(2, "0")
    return int(euros) * 100 + int(cents)
