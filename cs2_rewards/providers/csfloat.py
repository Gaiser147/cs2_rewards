"""CSFloat: offizielle Listings-API (https://docs.csfloat.com), API-Key nötig.

Preise kommen in US-Cent und werden mit EZB-Kurs + Sicherheitsaufschlag in
Euro umgerechnet. Gekauft wird nicht per API: Der offizielle Doku-Teil deckt
nur Suchen/Listen ab, deshalb öffnet das Tool den Angebotslink und Leonhard
kauft selbst auf der Website.
"""

import math
import random

import requests

from ..config import FX_SAFETY_MARGIN
from ..filters import Filters, Offer, is_allowed_item
from ..fx import usd_to_eur_rate

LISTINGS_URL = "https://csfloat.com/api/v1/listings"
ITEM_URL = "https://csfloat.com/item/{id}"
CATEGORY = {"any": 0, "no": 1, "yes": 2}


def eur_per_usd_cent(rate: float) -> float:
    return rate * (1 + FX_SAFETY_MARGIN)


def parse_listings(payload, factor: float, min_cents: int, max_cents: int, filters: Filters) -> list:
    listings = payload.get("data", []) if isinstance(payload, dict) else payload
    offers = []
    for listing in listings:
        item = listing.get("item", {})
        name = item.get("market_hash_name", "")
        if listing.get("type", "buy_now") != "buy_now":
            continue
        if item.get("type") not in (None, "skin") or not is_allowed_item(name):
            continue
        usd_cents = listing["price"]
        cents = math.ceil(usd_cents * factor)
        if not (min_cents <= cents <= max_cents) or not filters.matches(name):
            continue
        offers.append(
            Offer(
                name=name,
                price_cents=cents,
                link=ITEM_URL.format(id=listing["id"]),
                provider="csfloat",
                float_value=item.get("float_value"),
                original_price=f"${usd_cents / 100:.2f}",
            )
        )
    return offers


class CSFloatProvider:
    name = "csfloat"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def search(self, min_cents: int, max_cents: int, filters: Filters, count: int, rng: random.Random) -> list:
        factor = eur_per_usd_cent(usd_to_eur_rate())
        params = {
            "limit": 50,
            "sort_by": "best_deal",
            "type": "buy_now",
            "category": CATEGORY[filters.stattrak],
            "min_price": math.ceil(min_cents / factor),
            "max_price": math.floor(max_cents / factor),
        }
        resp = requests.get(LISTINGS_URL, params=params, headers={"Authorization": self._api_key}, timeout=20)
        resp.raise_for_status()
        offers = parse_listings(resp.json(), factor, min_cents, max_cents, filters)
        return rng.sample(offers, min(count, len(offers)))
