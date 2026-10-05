from dataclasses import dataclass
from typing import Optional

from .config import ALLOWED_CATEGORIES, BLOCKED_NAME_PREFIXES, BLOCKED_NAME_SUFFIXES

WEARS = {
    "fn": "Factory New",
    "mw": "Minimal Wear",
    "ft": "Field-Tested",
    "ww": "Well-Worn",
    "bs": "Battle-Scarred",
}


@dataclass
class Offer:
    name: str
    price_cents: int  # EUR, inkl. Sicherheitsaufschlag bei Fremdwährung
    link: str
    provider: str
    float_value: Optional[float] = None
    original_price: Optional[str] = None  # z. B. "$1.23" bei CSFloat

    @property
    def wear(self) -> Optional[str]:
        return wear_of(self.name)

    @property
    def stattrak(self) -> bool:
        return is_stattrak(self.name)


@dataclass
class Filters:
    weapon: Optional[str] = None
    wear: Optional[str] = None
    stattrak: str = "any"  # any | yes | no
    query: Optional[str] = None

    def matches(self, name: str) -> bool:
        lower = name.lower()
        if self.weapon and self.weapon.lower() not in weapon_of(name).lower():
            return False
        if self.wear and wear_of(name) != normalize_wear(self.wear):
            return False
        if self.stattrak == "yes" and not is_stattrak(name):
            return False
        if self.stattrak == "no" and is_stattrak(name):
            return False
        if self.query and self.query.lower() not in lower:
            return False
        return True


def normalize_wear(value: str) -> str:
    key = value.strip().lower()
    if key in WEARS:
        return WEARS[key]
    for full in WEARS.values():
        if full.lower() == key:
            return full
    raise ValueError(f"Unbekannter Zustand {value!r}. Erlaubt: {', '.join(WEARS)}")


def wear_of(name: str) -> Optional[str]:
    for full in WEARS.values():
        if name.endswith(f"({full})"):
            return full
    return None


def is_stattrak(name: str) -> bool:
    return "StatTrak" in name


def weapon_of(name: str) -> str:
    base = name.replace("StatTrak™ ", "").replace("Souvenir ", "").replace("★ ", "")
    return base.split(" | ")[0]


def is_allowed_item(name: str, category: Optional[str] = None) -> bool:
    """Nur konkrete Skins. Cases, Keys, Kapseln, Sticker usw. sind immer ausgeschlossen."""
    if category is not None and category not in ALLOWED_CATEGORIES:
        return False
    lower = name.lower().replace("stattrak™ ", "").replace("souvenir ", "")
    if lower.startswith(BLOCKED_NAME_PREFIXES) or lower.endswith(BLOCKED_NAME_SUFFIXES):
        return False
    # Ein konkreter Skin hat immer einen Zustand, Container und Kapseln nie.
    return " | " in name and wear_of(name) is not None
