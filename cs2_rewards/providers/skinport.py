"""Skinport: öffentliche API ohne Key, Preise direkt in EUR.

Die API liefert pro Skin den günstigsten Preis, aber keine Einzelangebote und
keinen Float. Kaufen geht nur auf der Website (über den Link).
"""

import json
import random
import time
from typing import Optional
from urllib.parse import urlparse

import requests

from ..config import data_dir
from ..filters import Filters, Offer, is_allowed_item
from ..money import eur_to_cents_ceil

ITEMS_URL = "https://api.skinport.com/v1/items"
CACHE_TTL_SECONDS = 300  # Skinport cached selbst 5 Minuten, Limit: 8 Anfragen / 5 Minuten


def category_of(market_page: str) -> Optional[str]:
    parts = urlparse(market_page).path.split("/")
    return parts[2] if len(parts) > 2 else None


def parse_items(items: list, min_cents: int, max_cents: int, filters: Filters) -> list:
    offers = []
    for it in items:
        price = it.get("min_price")
        if price is None or not it.get("quantity"):
            continue
        name = it["market_hash_name"]
        if not is_allowed_item(name, category_of(it.get("market_page", ""))):
            continue
        cents = eur_to_cents_ceil(price)
        if not (min_cents <= cents <= max_cents) or not filters.matches(name):
            continue
        offers.append(Offer(name=name, price_cents=cents, link=it["item_page"], provider="skinport"))
    return offers


class SkinportProvider:
    name = "skinport"

    def _fetch(self) -> list:
        cache = data_dir() / "cache" / "skinport_items.json"
        if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_SECONDS:
            return json.loads(cache.read_text(encoding="utf-8"))
        resp = requests.get(
            ITEMS_URL,
            params={"app_id": 730, "currency": "EUR", "tradable": 0},
            headers={"Accept-Encoding": "br"},
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(items), encoding="utf-8")
        return items

    def search(self, min_cents: int, max_cents: int, filters: Filters, count: int, rng: random.Random) -> list:
        offers = parse_items(self._fetch(), min_cents, max_cents, filters)
        return rng.sample(offers, min(count, len(offers)))
