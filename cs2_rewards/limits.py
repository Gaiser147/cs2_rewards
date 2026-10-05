from datetime import datetime

from .config import MONTHLY_LIMIT_CENTS, TIER_LIMITS_CENTS
from .ledger import Ledger
from .money import format_eur


class LimitError(Exception):
    pass


def monthly_remaining(ledger: Ledger, now: datetime) -> int:
    return max(0, MONTHLY_LIMIT_CENTS - ledger.spent_in_month(now.year, now.month))


def budget_for(tier: str, ledger: Ledger, now: datetime) -> int:
    """Höchstpreis für diesen Kauf: Stufenlimit, gedeckelt durch das restliche Monatsbudget."""
    return min(TIER_LIMITS_CENTS[tier], monthly_remaining(ledger, now))


def check_purchase(tier: str, price_cents: int, ledger: Ledger, now: datetime) -> None:
    tier_limit = TIER_LIMITS_CENTS[tier]
    if price_cents <= 0:
        raise LimitError("Preis muss größer als 0 sein.")
    if price_cents > tier_limit:
        raise LimitError(f"{format_eur(price_cents)} liegt über dem Limit für Stufe {tier} ({format_eur(tier_limit)}).")
    remaining = monthly_remaining(ledger, now)
    if price_cents > remaining:
        raise LimitError(
            f"{format_eur(price_cents)} würde das Monatslimit sprengen "
            f"(noch {format_eur(remaining)} von {format_eur(MONTHLY_LIMIT_CENTS)} frei)."
        )
