"""CSFloat: Listings-API (https://docs.csfloat.com), API-Key nötig.

Preise kommen in US-Cent und werden mit EZB-Kurs + Sicherheitsaufschlag in
Euro umgerechnet.

Kaufen (Geschenk-Modus) nutzt POST /api/v1/listings/buy. Dieser Endpunkt ist
NICHT offiziell dokumentiert (Format aus dem Wrapper Bios-Marcel/csfloat_go),
kann sich jederzeit ändern und verstößt womöglich gegen die Nutzungsbedingungen.
Leonhard hat das bewusst so entschieden.
"""

import math
import random

import requests

from ..config import FX_SAFETY_MARGIN
from ..filters import Filters, Offer, is_allowed_item
from ..fx import usd_to_eur_rate

LISTINGS_URL = "https://csfloat.com/api/v1/listings"
BUY_URL = "https://csfloat.com/api/v1/listings/buy"
ME_URL = "https://csfloat.com/api/v1/me"
ITEM_URL = "https://csfloat.com/item/{id}"
CATEGORY = {"any": 0, "no": 1, "yes": 2}


class BuyError(Exception):
    """retry=True: dieses Angebot ging nicht (z. B. schon verkauft), ein anderes darf versucht werden.
    retry=False: abbrechen, weil unklar ist, ob gekauft wurde, oder weil jeder weitere Versuch auch scheitert."""

    def __init__(self, message: str, retry: bool):
        super().__init__(message)
        self.retry = retry


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
                listing_id=str(listing["id"]),
                usd_cents=usd_cents,
            )
        )
    return offers


def _error_message(resp: requests.Response) -> str:
    try:
        return resp.json().get("message") or resp.text
    except ValueError:
        return resp.text or f"HTTP {resp.status_code}"


class CSFloatProvider:
    name = "csfloat"

    def __init__(self, api_key: str, session=None):
        self._api_key = api_key
        self._http = session or requests

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
        resp = self._http.get(LISTINGS_URL, params=params, headers={"Authorization": self._api_key}, timeout=20)
        resp.raise_for_status()
        offers = parse_listings(resp.json(), factor, min_cents, max_cents, filters)
        return rng.sample(offers, min(count, len(offers)))

    def balance_usd_cents(self):
        """Verfügbares CSFloat-Guthaben in US-Cent (GET /api/v1/me, Feld user.balance), None wenn unbekannt."""
        try:
            resp = self._http.get(ME_URL, headers={"Authorization": self._api_key}, timeout=20)
            resp.raise_for_status()
            return int(resp.json()["user"]["balance"])
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return None

    def buy(self, offer: Offer) -> None:
        """Kauft genau dieses Angebot zum angezeigten Preis. total_price schützt vor Preisänderungen."""
        if not offer.listing_id or offer.usd_cents is None:
            raise BuyError("Angebot ohne CSFloat-Listing-ID", retry=False)
        try:
            resp = self._http.post(
                BUY_URL,
                json={"contract_ids": [offer.listing_id], "total_price": offer.usd_cents},
                headers={"Authorization": self._api_key},
                timeout=30,
            )
        except requests.RequestException as e:
            # Keine Antwort heißt: Kauf eventuell trotzdem durchgegangen. Nie blind wiederholen.
            raise BuyError(f"Keine Antwort von CSFloat ({e}). Bitte im CSFloat-Konto nachsehen.", retry=False)
        if resp.ok:
            return
        message = _error_message(resp)
        if resp.status_code in (401, 402, 403) or resp.status_code >= 500 or "balance" in message.lower():
            raise BuyError(f"CSFloat: {message} (HTTP {resp.status_code})", retry=False)
        raise BuyError(f"CSFloat: {message} (HTTP {resp.status_code})", retry=True)
