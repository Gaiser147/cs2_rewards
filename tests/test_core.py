import json
from datetime import datetime
from pathlib import Path

import pytest

from cs2_rewards.filters import Filters, is_allowed_item, normalize_wear, weapon_of
from cs2_rewards.fx import parse_ecb_usd_to_eur
from cs2_rewards.ledger import Ledger
from cs2_rewards.limits import LimitError, budget_for, check_purchase
from cs2_rewards.money import format_eur, parse_eur
from cs2_rewards.providers.csfloat import eur_per_usd_cent, parse_listings
from cs2_rewards.providers.skinport import parse_items

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 5, 12, 0)


def ledger_with_spent(tmp_path, cents, when=NOW):
    ledger = Ledger(tmp_path / "ledger.json")
    r = ledger.add("XL", "früher", when)
    ledger.redeem(r, item="x", price_cents=cents, provider="test", link="", now=when)
    return ledger


@pytest.mark.parametrize(
    "text,cents",
    [("1,84", 184), ("1.84", 184), ("2", 200), ("0,5", 50), ("1,84 €", 184), (" 25 EUR ", 2500)],
)
def test_parse_eur(text, cents):
    assert parse_eur(text) == cents


@pytest.mark.parametrize("text", ["", "abc", "1,845", "-1", "1,2,3"])
def test_parse_eur_rejects(text):
    with pytest.raises(ValueError):
        parse_eur(text)


def test_format_eur():
    assert format_eur(184) == "1,84 €"
    assert format_eur(5) == "0,05 €"


def test_tier_limit_enforced(tmp_path):
    ledger = Ledger(tmp_path / "l.json")
    check_purchase("S", 50, ledger, NOW)
    with pytest.raises(LimitError):
        check_purchase("S", 51, ledger, NOW)
    with pytest.raises(LimitError):
        check_purchase("M", 0, ledger, NOW)


def test_monthly_limit_enforced(tmp_path):
    ledger = ledger_with_spent(tmp_path, 2500)
    check_purchase("L", 500, ledger, NOW)
    with pytest.raises(LimitError, match="Monatslimit"):
        check_purchase("L", 501, ledger, NOW)
    assert budget_for("L", ledger, NOW) == 500
    assert budget_for("S", ledger, NOW) == 50


def test_previous_month_does_not_count(tmp_path):
    ledger = ledger_with_spent(tmp_path, 2500, when=datetime(2026, 9, 30, 23, 59))
    assert budget_for("XL", ledger, NOW) == 2500


def test_ledger_roundtrip(tmp_path):
    path = tmp_path / "sub" / "ledger.json"
    ledger = Ledger(path)
    r = ledger.add("M", "Boss Gleichungen", NOW)
    ledger.save()
    loaded = Ledger.load(path)
    assert loaded.get(r.id).reason == "Boss Gleichungen"
    assert [x.id for x in loaded.open_rewards()] == [r.id]


@pytest.mark.parametrize(
    "name,allowed",
    [
        ("AK-47 | Redline (Field-Tested)", True),
        ("StatTrak™ AK-47 | Redline (Well-Worn)", True),
        ("★ Karambit | Case Hardened (Field-Tested)", True),
        ("Five-SeveN | Case Hardened (Minimal Wear)", True),
        ("Revolution Case", False),
        ("Operation Hydra Case Key", False),
        ("10 Year Birthday Sticker Capsule", False),
        ("Sticker | Blitzkrieg", False),
        ("Charm | Big Brain", False),
        ("Souvenir Package Paris 2023", False),
        ("Sealed Graffiti | Lambda (Blood Red)", False),
    ],
)
def test_is_allowed_item(name, allowed):
    assert is_allowed_item(name) is allowed


def test_blocked_category():
    assert not is_allowed_item("AK-47 | Redline (Field-Tested)", "container")


def test_filters():
    f = Filters(weapon="ak-47", wear="ft", stattrak="no")
    assert f.matches("AK-47 | Redline (Field-Tested)")
    assert not f.matches("StatTrak™ AK-47 | Redline (Field-Tested)")
    assert not f.matches("AK-47 | Redline (Minimal Wear)")
    assert not f.matches("AWP | Redline (Field-Tested)")
    assert Filters(query="neon").matches("AK-47 | Neon Rider (Field-Tested)")
    assert weapon_of("★ StatTrak™ Karambit | Fade (Factory New)") == "Karambit"
    assert normalize_wear("Minimal Wear") == "Minimal Wear"
    with pytest.raises(ValueError):
        normalize_wear("neu")


def test_skinport_parse_only_skins_in_budget():
    items = json.loads((FIXTURES / "skinport_items.json").read_text(encoding="utf-8"))
    offers = parse_items(items, 20, 200, Filters())
    names = {o.name for o in offers}
    assert names, "Fixture sollte Treffer enthalten"
    assert all(20 <= o.price_cents <= 200 for o in offers)
    assert all(is_allowed_item(n) for n in names)
    assert not any("Capsule" in n or "Key" in n or "Charm" in n or "Sticker" in n for n in names)
    assert all(o.link.startswith("https://skinport.com/item/") for o in offers)


def test_csfloat_parse_converts_and_filters():
    payload = json.loads((FIXTURES / "csfloat_listings.json").read_text())
    factor = eur_per_usd_cent(0.9)  # 0.927 EUR pro USD-Cent inkl. Aufschlag
    offers = parse_listings(payload, factor, 80, 200, Filters())
    by_name = {o.name: o for o in offers}
    # Auktion, Case und zu teurer Skin fallen raus
    assert set(by_name) == {"MAC-10 | Allure (Field-Tested)", "StatTrak™ Glock-18 | Clear Polymer (Minimal Wear)"}
    mac = by_name["MAC-10 | Allure (Field-Tested)"]
    assert mac.price_cents == 140  # ceil(150 * 0.927)
    assert mac.link == "https://csfloat.com/item/900000000000000001"
    assert mac.float_value == pytest.approx(0.2213)
    # Ältere Antwortform (reine Liste) wird auch verstanden
    assert parse_listings(payload["data"], factor, 80, 200, Filters()) != []


def test_parse_ecb():
    xml = """<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
      xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref"><Cube><Cube time="2026-10-02">
      <Cube currency="USD" rate="1.25"/><Cube currency="JPY" rate="160"/></Cube></Cube></gesmes:Envelope>"""
    assert parse_ecb_usd_to_eur(xml) == pytest.approx(0.8)
