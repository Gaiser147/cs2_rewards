"""reward – Lern-Belohnungen in CS2-Skins einlösen.

  reward claim M "Boss Gleichungen"     Belohnung eintragen und direkt einlösen
  reward redeem 3                       offene Belohnung später einlösen
  reward status                         Übersicht und Monatsbudget

Mit CSFLOAT_AUTO_BUY=1 (Geschenk-Modus) wählt und kauft das Tool selbst,
sonst zeigt es Vorschläge und Leonhard kauft auf der Website.
"""

import argparse
import random
import sys
import webbrowser
from datetime import datetime

from dotenv import load_dotenv

from .config import MIN_PRICE_SHARE, MONTHLY_LIMIT_CENTS, TIER_LIMITS_CENTS
from .filters import WEARS, Filters, normalize_wear
from .ledger import OPEN, Ledger
from .limits import LimitError, budget_for, check_purchase, monthly_remaining
from .money import format_eur, parse_eur
from .providers import auto_buy_enabled, get_provider
from .providers.csfloat import BuyError

# Höchstens so viele Angebote nacheinander versuchen, falls eins schon weg ist.
MAX_BUY_ATTEMPTS = 3


class Console:
    """Ein-/Ausgabe als Objekt, damit Tests den Dialog durchspielen können."""

    def __init__(self, input_fn=input, print_fn=print, open_fn=webbrowser.open):
        self.input = input_fn
        self.print = print_fn
        self.open = open_fn


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reward", description="Lern-Belohnungen in CS2-Skins einlösen.")
    sub = p.add_subparsers(dest="command", required=True)

    def add_search_options(sp):
        sp.add_argument("--weapon", help="Waffe, z. B. AK-47, AWP, Glock")
        sp.add_argument("--wear", help=f"Zustand: {', '.join(WEARS)}")
        sp.add_argument("--stattrak", choices=["any", "yes", "no"], default="any", help="StatTrak (Standard: egal)")
        sp.add_argument("--query", help="Freitext im Skin-Namen, z. B. 'Neon' oder 'Asiimov'")
        sp.add_argument("--provider", choices=["auto", "csfloat", "skinport"], default="auto")
        sp.add_argument("--count", type=int, default=5, choices=range(1, 11), metavar="1-10")
        sp.add_argument("--seed", type=int, help="feste Zufallsauswahl (zum Testen)")
        sp.add_argument("--dry-run", action="store_true", help="nur Vorschläge zeigen, nichts öffnen oder buchen")

    claim = sub.add_parser("claim", help="vergebene Belohnung eintragen und einlösen")
    claim.add_argument("tier", type=str.upper, choices=list(TIER_LIMITS_CENTS))
    claim.add_argument("reason")
    add_search_options(claim)

    redeem = sub.add_parser("redeem", help="offene Belohnung einlösen")
    redeem.add_argument("id", type=int)
    add_search_options(redeem)

    sub.add_parser("status", help="Übersicht anzeigen")
    return p


def cmd_status(ledger: Ledger, now: datetime, con: Console) -> int:
    spent = ledger.spent_in_month(now.year, now.month)
    con.print(f"Monatsbudget {now:%m/%Y}: {format_eur(spent)} von {format_eur(MONTHLY_LIMIT_CENTS)} verbraucht")
    if not ledger.rewards:
        con.print("Noch keine Belohnungen.")
        return 0
    con.print("")
    for r in ledger.rewards:
        date = (r.redeemed_at or r.earned_at)[:10]
        if r.status == OPEN:
            con.print(f"#{r.id:<3} {date}  {r.tier:<2}  OFFEN    {r.reason}")
        else:
            con.print(f"#{r.id:<3} {date}  {r.tier:<2}  {format_eur(r.price_cents):>8}  {r.reason} -> {r.item}")
    open_ids = [f"#{r.id}" for r in ledger.open_rewards()]
    if open_ids:
        con.print(f"\nOffen: {', '.join(open_ids)} (einlösen mit: reward redeem <ID>)")
    return 0


def buy_gift(ledger: Ledger, reward, offers: list, provider, now: datetime, con: Console, dry_run: bool) -> int:
    """Geschenk-Modus: Claude kauft ohne Rückfrage, die harten Limits gelten trotzdem."""
    balance = provider.balance_usd_cents() if hasattr(provider, "balance_usd_cents") else None
    if balance is not None:
        con.print(f"CSFloat-Guthaben: ${balance / 100:.2f}")
        affordable = [o for o in offers if o.usd_cents is None or o.usd_cents <= balance]
        if not affordable:
            con.print(f"Guthaben reicht für keins der Angebote. Belohnung #{reward.id} bleibt offen.")
            return 1
        offers = affordable
    if dry_run:
        con.print(f"Dry-Run: Geschenk wäre {offers[0].name} für {format_eur(offers[0].price_cents)}. Nichts gekauft.")
        return 0
    for offer in offers[:MAX_BUY_ATTEMPTS]:
        try:
            check_purchase(reward.tier, offer.price_cents, ledger, now)
        except LimitError as e:
            con.print(f"Übersprungen: {e}")
            continue
        try:
            provider.buy(offer)
        except BuyError as e:
            con.print(f"Kauf fehlgeschlagen: {e}")
            if not e.retry:
                con.print(f"Belohnung #{reward.id} bleibt offen. Bitte im CSFloat-Konto prüfen, ob doch gekauft wurde.")
                return 1
            continue
        ledger.redeem(reward, item=offer.name, price_cents=offer.price_cents, provider=offer.provider, link=offer.link, now=now)
        ledger.save()
        con.print("")
        con.print(f"🎁 Geschenk für „{reward.reason}“: {offer.name}")
        con.print(f"   {format_eur(offer.price_cents)}  {offer.link}")
        if balance is not None and offer.usd_cents is not None:
            con.print(f"   Vom Guthaben abgezogen: {offer.original_price}, übrig ca. ${(balance - offer.usd_cents) / 100:.2f}")
        con.print("Der Verkäufer schickt dir jetzt ein Steam-Trade-Angebot. Nimm es in der Steam-App an.")
        con.print(f"Monatsbudget noch frei: {format_eur(monthly_remaining(ledger, now))}.")
        return 0
    con.print(f"Kein Kauf hat geklappt. Belohnung #{reward.id} bleibt offen, später nochmal: reward redeem {reward.id}")
    return 1


def redeem(ledger: Ledger, reward, args, provider, now: datetime, con: Console, gift: bool = False) -> int:
    budget = budget_for(reward.tier, ledger, now)
    if budget <= 0:
        con.print(f"Monatslimit ({format_eur(MONTHLY_LIMIT_CENTS)}) ist erreicht. Belohnung #{reward.id} bleibt offen.")
        return 1
    min_cents = int(budget * MIN_PRICE_SHARE)
    filters = Filters(weapon=args.weapon, wear=args.wear, stattrak=args.stattrak, query=args.query)
    rng = random.Random(args.seed)

    con.print(f"Belohnung #{reward.id} ({reward.tier}: {reward.reason})")
    con.print(f"Suche auf {provider.name}: {format_eur(min_cents)} bis {format_eur(budget)} …")
    offers = provider.search(min_cents, budget, filters, args.count, rng)
    if not offers:
        con.print("Keine passenden Angebote gefunden. Filter lockern oder später nochmal versuchen.")
        con.print(f"Belohnung #{reward.id} bleibt offen.")
        return 1

    if gift:
        return buy_gift(ledger, reward, offers, provider, now, con, dry_run=args.dry_run)

    offers.sort(key=lambda o: o.price_cents)
    con.print("")
    for i, o in enumerate(offers, 1):
        details = []
        if o.float_value is not None:
            details.append(f"Float {o.float_value:.4f}")
        if o.original_price:
            details.append(o.original_price)
        extra = f"  ({', '.join(details)})" if details else ""
        con.print(f"  [{i}] {format_eur(o.price_cents):>8}  {o.name}{extra}")
        con.print(f"       {o.link}")
    con.print("")

    if args.dry_run:
        con.print("Dry-Run: nichts geöffnet, nichts gebucht.")
        return 0

    choice = con.input(f"Welcher Skin? [1-{len(offers)}, Enter = abbrechen] ").strip()
    if not choice:
        con.print(f"Abgebrochen. Belohnung #{reward.id} bleibt offen.")
        return 0
    if not choice.isdigit() or not 1 <= int(choice) <= len(offers):
        con.print("Ungültige Auswahl. Abgebrochen.")
        return 1
    offer = offers[int(choice) - 1]

    try:
        check_purchase(reward.tier, offer.price_cents, ledger, now)
    except LimitError as e:
        con.print(f"Verweigert: {e}")
        return 1

    typed = con.input(f"Zur Bestätigung den Preis eintippen ({format_eur(offer.price_cents)}): ")
    try:
        if parse_eur(typed) != offer.price_cents:
            raise ValueError
    except ValueError:
        con.print("Preis stimmt nicht überein. Abgebrochen.")
        return 1

    con.print(f"Öffne {offer.link}")
    con.print("Kaufe dort selbst. Danach kommt ein Steam-Trade-Angebot, das du in Steam annimmst.")
    con.open(offer.link)

    paid = con.input("Bezahlten Preis in € eingeben (Enter = doch nicht gekauft): ").strip()
    if not paid:
        con.print(f"Nicht gebucht. Belohnung #{reward.id} bleibt offen.")
        return 0
    try:
        paid_cents = parse_eur(paid)
        check_purchase(reward.tier, paid_cents, ledger, now)
    except (ValueError, LimitError) as e:
        con.print(f"Nicht gebucht: {e}")
        return 1

    ledger.redeem(reward, item=offer.name, price_cents=paid_cents, provider=offer.provider, link=offer.link, now=now)
    ledger.save()
    rest = monthly_remaining(ledger, now)
    con.print(f"Gebucht: {offer.name} für {format_eur(paid_cents)}. Monatsbudget noch frei: {format_eur(rest)}.")
    return 0


def main(argv=None, con: Console = None, ledger: Ledger = None, provider=None, now: datetime = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    con = con or Console()
    ledger = ledger if ledger is not None else Ledger.load()
    now = now or datetime.now()

    if args.command == "status":
        return cmd_status(ledger, now, con)

    if args.wear:
        try:
            normalize_wear(args.wear)
        except ValueError as e:
            con.print(str(e))
            return 2

    if args.command == "claim":
        reward = ledger.add(args.tier, args.reason, now)
        if not args.dry_run:
            ledger.save()
            con.print(f"Belohnung #{reward.id} eingetragen.")
    else:
        try:
            reward = ledger.get(args.id)
        except KeyError as e:
            con.print(str(e.args[0]))
            return 1
        if reward.status != OPEN:
            con.print(f"Belohnung #{reward.id} wurde schon eingelöst.")
            return 1

    try:
        provider = provider or get_provider(args.provider)
        gift = auto_buy_enabled() and hasattr(provider, "buy")
        if auto_buy_enabled() and not gift:
            con.print(f"Geschenk-Modus geht nur mit CSFloat. Auf {provider.name} kaufst du selbst.")
        return redeem(ledger, reward, args, provider, now, con, gift=gift)
    except Exception as e:  # Netzwerk, fehlender Key, API-Fehler
        con.print(f"Fehler: {e}")
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status in (401, 403):
            con.print("API-Key ungültig oder abgelaufen? Ausweichen mit: --provider skinport")
        if not args.dry_run:
            con.print(f"Belohnung #{reward.id} bleibt offen (reward redeem {reward.id}).")
        return 1


if __name__ == "__main__":
    sys.exit(main())
