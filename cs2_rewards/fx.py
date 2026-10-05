"""USD->EUR über den offiziellen EZB-Referenzkurs (ohne API-Key)."""

import json
import xml.etree.ElementTree as ET
from datetime import date

import requests

from .config import FALLBACK_USD_TO_EUR, data_dir

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


def parse_ecb_usd_to_eur(xml_text: str) -> float:
    for el in ET.fromstring(xml_text).iter():
        if el.attrib.get("currency") == "USD":
            return 1 / float(el.attrib["rate"])  # EZB liefert 1 EUR = x USD
    raise ValueError("USD-Kurs nicht in der EZB-Antwort gefunden")


def usd_to_eur_rate() -> float:
    cache = data_dir() / "cache" / "usd_eur.json"
    today = date.today().isoformat()
    try:
        cached = json.loads(cache.read_text())
        if cached["date"] == today:
            return cached["rate"]
    except (OSError, ValueError, KeyError):
        pass
    try:
        resp = requests.get(ECB_URL, timeout=10)
        resp.raise_for_status()
        rate = parse_ecb_usd_to_eur(resp.text)
    except (requests.RequestException, ValueError):
        return FALLBACK_USD_TO_EUR
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"date": today, "rate": rate}))
    return rate
