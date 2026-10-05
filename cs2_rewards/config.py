"""Harte Limits und feste Einstellungen.

Die Limits stehen absichtlich im Code und nicht in der .env: Änderungen sollen
bewusst (per Commit) passieren und nicht nebenbei.
Alle Beträge in Euro-Cent.
"""

import os
from pathlib import Path

TIER_LIMITS_CENTS = {
    "S": 50,  # Übungspaket überwiegend richtig
    "M": 200,  # Boss-Aufgabe auf Klausurniveau
    "L": 800,  # ganzes Thema abgeschlossen
    "XL": 2500,  # Brückenkurs komplett fertig
}

MONTHLY_LIMIT_CENTS = 3000

# Vorschläge sollen sich nach Belohnung anfühlen: nicht nur Ramsch für 3 Cent.
MIN_PRICE_SHARE = 0.4

# Aufschlag auf umgerechnete USD-Preise (Kursschwankung, Kartengebühr bei Einzahlung).
FX_SAFETY_MARGIN = 0.03
# Wird nur genutzt, wenn der EZB-Kurs nicht abrufbar ist; bewusst ungünstig gewählt.
FALLBACK_USD_TO_EUR = 1.0

# Nur echte Waffen-Skins, Messer und Handschuhe. Keine Cases, Keys, Kapseln usw.
ALLOWED_CATEGORIES = {"rifle", "pistol", "smg", "heavy", "knife", "gloves"}
# Zusätzliche Sperre über den Namen, falls ein Marktplatz keine Kategorie liefert.
BLOCKED_NAME_PREFIXES = ("sticker |", "sealed graffiti |", "graffiti |", "patch |", "charm |", "music kit |")
BLOCKED_NAME_SUFFIXES = (" case", " key", " capsule", " package", " pass", " pin")


def data_dir() -> Path:
    return Path(os.environ.get("REWARD_HOME", Path.home() / ".cs2_rewards"))
