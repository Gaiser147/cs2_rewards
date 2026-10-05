"""Geschenk-Modus: automatischer Kauf auf CSFloat. Alles gegen Fakes, nie gegen die echte API."""

from datetime import datetime

import pytest
import requests

from cs2_rewards.cli import main
from cs2_rewards.filters import Offer
from cs2_rewards.ledger import OPEN, REDEEMED, Ledger
from cs2_rewards.providers.csfloat import BUY_URL, BuyError, CSFloatProvider

from test_cli import FakeProvider, Script

NOW = datetime(2026, 10, 5, 12, 0)


def csf_offer(name, cents, listing_id="L1"):
    return Offer(
        name=name,
        price_cents=cents,
        link=f"https://csfloat.com/item/{listing_id}",
        provider="csfloat",
        listing_id=listing_id,
        usd_cents=cents,
    )


class FakeBuyer(FakeProvider):
    name = "csfloat"

    def __init__(self, offers, results):
        super().__init__(offers)
        self.results = list(results)  # pro Kaufversuch: None = ok, sonst BuyError
        self.bought = []

    def buy(self, offer):
        self.bought.append(offer.listing_id)
        result = self.results.pop(0)
        if result:
            raise result


@pytest.fixture(autouse=True)
def gift_mode(monkeypatch):
    monkeypatch.setenv("CSFLOAT_AUTO_BUY", "1")


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.json")


def run(argv, ledger, provider):
    con = Script([])  # Geschenk-Modus fragt nichts: jede Eingabe würde den Test sprengen
    code = main(argv, con=con, ledger=ledger, provider=provider, now=NOW)
    return code, con


def test_gift_buys_without_questions(ledger):
    provider = FakeBuyer([csf_offer("MAC-10 | Allure (Field-Tested)", 150, "A")], [None])
    code, con = run(["claim", "M", "Boss Gleichungen"], ledger, provider)
    assert code == 0
    assert provider.bought == ["A"]
    assert con.opened == []
    r = Ledger.load(ledger.path).rewards[0]
    assert (r.status, r.price_cents, r.provider) == (REDEEMED, 150, "csfloat")
    assert "🎁" in con.text and "Steam" in con.text


def test_gift_tries_next_offer_when_sold(ledger):
    offers = [csf_offer("A | B (Field-Tested)", 150, "A"), csf_offer("C | D (Field-Tested)", 160, "C")]
    provider = FakeBuyer(offers, [BuyError("listing sold", retry=True), None])
    code, _ = run(["claim", "M", "x"], ledger, provider)
    assert code == 0
    assert provider.bought == ["A", "C"]
    assert Ledger.load(ledger.path).rewards[0].item == "C | D (Field-Tested)"


def test_gift_stops_on_unclear_result(ledger):
    offers = [csf_offer("A | B (Field-Tested)", 150, "A"), csf_offer("C | D (Field-Tested)", 160, "C")]
    provider = FakeBuyer(offers, [BuyError("timeout", retry=False)])
    code, con = run(["claim", "M", "x"], ledger, provider)
    assert code == 1
    assert provider.bought == ["A"]  # nicht blind das nächste kaufen
    assert Ledger.load(ledger.path).rewards[0].status == OPEN
    assert "CSFloat-Konto" in con.text


def test_gift_gives_up_after_max_attempts(ledger):
    offers = [csf_offer(f"W{i} | S (Field-Tested)", 150, str(i)) for i in range(5)]
    provider = FakeBuyer(offers, [BuyError("sold", retry=True)] * 5)
    code, _ = run(["claim", "M", "x"], ledger, provider)
    assert code == 1
    assert len(provider.bought) == 3


def test_gift_respects_monthly_limit(ledger):
    prev = ledger.add("XL", "früher", NOW)
    ledger.redeem(prev, item="x", price_cents=3000, provider="t", link="", now=NOW)
    provider = FakeBuyer([csf_offer("A | B (Field-Tested)", 40)], [None])
    code, _ = run(["claim", "S", "x"], ledger, provider)
    assert code == 1
    assert provider.bought == []


def test_gift_dry_run_buys_nothing(ledger):
    provider = FakeBuyer([csf_offer("A | B (Field-Tested)", 150)], [])
    code, con = run(["claim", "M", "x", "--dry-run"], ledger, provider)
    assert code == 0
    assert provider.bought == []
    assert "Nichts gekauft" in con.text


def test_gift_mode_off_falls_back_to_manual(ledger, monkeypatch):
    monkeypatch.delenv("CSFLOAT_AUTO_BUY")
    provider = FakeBuyer([csf_offer("A | B (Field-Tested)", 150)], [])
    con = Script([""])  # manueller Modus fragt nach Auswahl, Enter = abbrechen
    code = main(["claim", "M", "x"], con=con, ledger=ledger, provider=provider, now=NOW)
    assert code == 0
    assert provider.bought == []


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self.ok = status < 400
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response, exc, []

    def post(self, url, json, headers, timeout):
        self.calls.append((url, json, headers))
        if self.exc:
            raise self.exc
        return self.response


def test_buy_request_format():
    session = FakeSession(FakeResponse(200, {"message": "ok"}))
    CSFloatProvider("KEY", session=session).buy(csf_offer("A | B (Field-Tested)", 140, "123"))
    url, body, headers = session.calls[0]
    assert url == BUY_URL == "https://csfloat.com/api/v1/listings/buy"
    assert body == {"contract_ids": ["123"], "total_price": 140}
    assert headers == {"Authorization": "KEY"}


@pytest.mark.parametrize(
    "status,body,retry",
    [
        (400, {"message": "listing is no longer available"}, True),
        (400, {"message": "insufficient balance"}, False),
        (401, {"message": "unauthorized"}, False),
        (500, {"message": "internal"}, False),
    ],
)
def test_buy_errors(status, body, retry):
    provider = CSFloatProvider("KEY", session=FakeSession(FakeResponse(status, body)))
    with pytest.raises(BuyError) as e:
        provider.buy(csf_offer("A | B (Field-Tested)", 140))
    assert e.value.retry is retry


def test_buy_network_error_never_retries():
    provider = CSFloatProvider("KEY", session=FakeSession(exc=requests.Timeout("slow")))
    with pytest.raises(BuyError) as e:
        provider.buy(csf_offer("A | B (Field-Tested)", 140))
    assert e.value.retry is False
