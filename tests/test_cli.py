from datetime import datetime

import pytest

from cs2_rewards.cli import Console, main
from cs2_rewards.filters import Offer
from cs2_rewards.ledger import OPEN, REDEEMED, Ledger

NOW = datetime(2026, 10, 5, 12, 0)


class FakeProvider:
    name = "fake"

    def __init__(self, offers):
        self.offers = offers
        self.calls = []

    def search(self, min_cents, max_cents, filters, count, rng):
        self.calls.append((min_cents, max_cents))
        return [o for o in self.offers if min_cents <= o.price_cents <= max_cents][:count]


def offer(name, cents):
    return Offer(name=name, price_cents=cents, link=f"https://example.test/{cents}", provider="fake")


class Script(Console):
    def __init__(self, answers):
        self.answers = list(answers)
        self.out = []
        self.opened = []
        super().__init__(self._input, self.out.append, self.opened.append)

    def _input(self, prompt=""):
        self.out.append(prompt)
        return self.answers.pop(0)

    @property
    def text(self):
        return "\n".join(map(str, self.out))


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.json")


def run(argv, answers, ledger, offers):
    con = Script(answers)
    provider = FakeProvider(offers)
    code = main(argv, con=con, ledger=ledger, provider=provider, now=NOW)
    return code, con, provider


def test_claim_happy_path(ledger):
    offers = [offer("MAC-10 | Allure (Field-Tested)", 150), offer("P250 | Sand Dune (Factory New)", 180)]
    code, con, provider = run(["claim", "m", "Boss Gleichungen"], ["2", "1,80", "1,80"], ledger, offers)
    assert code == 0
    assert provider.calls == [(80, 200)]
    assert con.opened == ["https://example.test/180"]
    r = Ledger.load(ledger.path).rewards[0]
    assert (r.status, r.tier, r.price_cents, r.item) == (REDEEMED, "M", 180, "P250 | Sand Dune (Factory New)")


def test_wrong_confirmation_price_aborts(ledger):
    code, con, _ = run(["claim", "M", "x"], ["1", "1,00"], ledger, [offer("A | B (Field-Tested)", 150)])
    assert code == 1
    assert con.opened == []
    assert Ledger.load(ledger.path).rewards[0].status == OPEN


def test_paid_price_over_limit_not_booked(ledger):
    code, con, _ = run(["claim", "S", "x"], ["1", "0,40", "0,90"], ledger, [offer("A | B (Field-Tested)", 40)])
    assert code == 1
    assert "Limit" in con.text
    assert Ledger.load(ledger.path).rewards[0].status == OPEN


def test_cancel_keeps_reward_open_and_redeem_later(ledger):
    offers = [offer("A | B (Field-Tested)", 150)]
    code, _, _ = run(["claim", "M", "x"], [""], ledger, offers)
    assert code == 0
    assert ledger.rewards[0].status == OPEN
    code, _, _ = run(["redeem", "1"], ["1", "1,50", "1,50"], ledger, offers)
    assert code == 0
    assert Ledger.load(ledger.path).rewards[0].status == REDEEMED
    code, con, _ = run(["redeem", "1"], [], ledger, offers)
    assert code == 1 and "schon eingelöst" in con.text


def test_monthly_limit_caps_search_budget(ledger):
    prev = ledger.add("XL", "früher", NOW)
    ledger.redeem(prev, item="x", price_cents=2900, provider="t", link="", now=NOW)
    _, _, provider = run(["claim", "L", "Thema Logik", "--dry-run"], [], ledger, [])
    assert provider.calls == [(40, 100)]


def test_monthly_limit_reached(ledger):
    prev = ledger.add("XL", "früher", NOW)
    ledger.redeem(prev, item="x", price_cents=3000, provider="t", link="", now=NOW)
    code, con, provider = run(["claim", "S", "x"], [], ledger, [offer("A | B (Field-Tested)", 40)])
    assert code == 1
    assert provider.calls == []
    assert "Monatslimit" in con.text


def test_dry_run_saves_nothing(ledger):
    code, con, _ = run(["claim", "S", "x", "--dry-run"], [], ledger, [offer("A | B (Field-Tested)", 40)])
    assert code == 0
    assert con.opened == []
    assert not ledger.path.exists()


def test_status(ledger):
    r = ledger.add("M", "Boss", NOW)
    ledger.redeem(r, item="MAC-10 | Allure (Field-Tested)", price_cents=150, provider="t", link="", now=NOW)
    ledger.add("S", "Übung Mengen", NOW)
    code, con, _ = run(["status"], [], ledger, [])
    assert code == 0
    assert "1,50 € von 30,00 €" in con.text
    assert "OFFEN" in con.text and "#2" in con.text
