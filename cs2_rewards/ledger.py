"""Lokales JSON-Protokoll aller Belohnungen."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import data_dir

OPEN = "open"
REDEEMED = "redeemed"


@dataclass
class Reward:
    id: int
    tier: str
    reason: str
    earned_at: str
    status: str = OPEN
    redeemed_at: Optional[str] = None
    item: Optional[str] = None
    price_cents: Optional[int] = None
    provider: Optional[str] = None
    link: Optional[str] = None


@dataclass
class Ledger:
    path: Path
    rewards: list = field(default_factory=list)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Ledger":
        path = path or data_dir() / "ledger.json"
        if not path.exists():
            return cls(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(path, [Reward(**r) for r in raw.get("rewards", [])])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"rewards": [asdict(r) for r in self.rewards]}
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def add(self, tier: str, reason: str, now: datetime) -> Reward:
        next_id = max((r.id for r in self.rewards), default=0) + 1
        reward = Reward(id=next_id, tier=tier, reason=reason, earned_at=now.isoformat(timespec="seconds"))
        self.rewards.append(reward)
        return reward

    def get(self, reward_id: int) -> Reward:
        for r in self.rewards:
            if r.id == reward_id:
                return r
        raise KeyError(f"Keine Belohnung mit ID {reward_id}")

    def open_rewards(self) -> list:
        return [r for r in self.rewards if r.status == OPEN]

    def spent_in_month(self, year: int, month: int) -> int:
        total = 0
        for r in self.rewards:
            if r.status == REDEEMED and r.redeemed_at:
                d = datetime.fromisoformat(r.redeemed_at)
                if (d.year, d.month) == (year, month):
                    total += r.price_cents or 0
        return total

    def redeem(self, reward: Reward, *, item: str, price_cents: int, provider: str, link: str, now: datetime) -> None:
        reward.status = REDEEMED
        reward.redeemed_at = now.isoformat(timespec="seconds")
        reward.item = item
        reward.price_cents = price_cents
        reward.provider = provider
        reward.link = link
