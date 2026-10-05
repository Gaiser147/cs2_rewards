# cs2-rewards

Kleines Kommandozeilen-Tool für das Lern-Belohnungssystem: Wenn Claude im Mathe-Chat eine Belohnung vergibt (`🎁 REWARD: M – Boss Gleichungen gelöst`), löst Leonhard sie hier ein. Das Tool sucht passende CS2-Skins im Budget, Leonhard wählt einen aus und kauft ihn selbst auf der Website. Danach wird alles protokolliert.

## Regeln im Code

| Stufe | Wofür | max. Preis |
|---|---|---|
| S | Übungspaket überwiegend richtig | 0,50 € |
| M | Boss-Aufgabe auf Klausurniveau | 2,00 € |
| L | ganzes Thema abgeschlossen | 8,00 € |
| XL | Brückenkurs fertig vor Vorlesungsstart | 25,00 € |

- **Monatslimit: 30 €** für alle Käufe zusammen (Kalendermonat).
- Die Limits stehen in `cs2_rewards/config.py`. Ändern geht nur per Code-Änderung, nicht über die `.env`.
- Es werden nur konkrete Waffen-Skins, Messer und Handschuhe vorgeschlagen. **Cases, Keys, Kapseln, Sticker und Pakete sind immer ausgeschlossen.**
- Kein Auto-Kauf: Jeder Kauf braucht eine Auswahl, das Eintippen des Preises und den Klick auf „Kaufen“ auf der Website.
- Liegt ein Preis über dem Stufen- oder Monatslimit, verweigert das Tool den Kauf, auch beim nachträglichen Eintragen des bezahlten Preises.

## Einrichtung

Voraussetzung: Python 3.10 oder neuer.

```bash
git clone https://github.com/gaiser147/cs2_rewards.git
cd cs2_rewards
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[keyring]"
```

### CSFloat-API-Key (optional, empfohlen)

Ohne Key nutzt das Tool Skinport. Das funktioniert sofort, zeigt aber keine Float-Werte. Mit Key sucht es auf CSFloat:

1. csfloat.com → mit Steam einloggen → Profil → Tab **Developer** → Key erstellen
2. Den Key **eine** dieser beiden Arten hinterlegen:
   - im System-Keyring (sicherer): `python -m keyring set cs2_rewards csfloat_api_key`
   - in einer `.env`: `.env.example` nach `.env` kopieren und `CSFLOAT_API_KEY=...` eintragen. Die `.env` ist in `.gitignore` und wird nie committet.

### Steam

Kurzfassung (Details in [docs/RESEARCH.md](docs/RESEARCH.md#steam-was-leonhard-einrichten-muss)):

1. Steam Guard Mobile Authenticator aktivieren
2. Trade-URL im CSFloat- bzw. Skinport-Profil eintragen
3. Inventar auf öffentlich stellen
4. Gekaufte Skins sind nach dem Annehmen sofort nutzbar, wegen Steams Trade-Schutz aber erst nach 7 Tagen weiterhandelbar

## Benutzung

```bash
# Belohnung aus dem Chat eintragen und gleich einlösen
reward claim M "Boss Gleichungen"

# mit Wunschfiltern
reward claim L "Thema Logik" --weapon AK-47 --wear ft --stattrak no
reward claim S "Übung Mengen" --query Neon

# nur schauen, nichts buchen
reward claim M "Test" --dry-run

# später einlösen (wenn vorher abgebrochen) und Übersicht
reward redeem 3
reward status
```

Ablauf bei `claim`:

1. Die Belohnung wird als **offen** eingetragen.
2. Das Tool zeigt bis zu 5 Vorschläge zwischen 40 % und 100 % des Budgets, mit Preis, Link und (bei CSFloat) Float.
3. Du wählst eine Nummer und tippst zur Bestätigung den Preis ein.
4. Der Link öffnet sich im Browser, dort kaufst du selbst.
5. Den Steam-Trade nimmst du in der Steam-App an.
6. Im Tool trägst du den tatsächlich bezahlten Preis ein. Damit ist die Belohnung eingelöst und im Ledger protokolliert.

Wer bei Schritt 3 oder 6 einfach Enter drückt, bricht ab. Die Belohnung bleibt dann offen.

Optionen: `--weapon`, `--wear` (`fn`, `mw`, `ft`, `ww`, `bs`), `--stattrak any|yes|no`, `--query` (Freitext im Namen, ein Farbfilter existiert in den APIs nicht), `--provider auto|csfloat|skinport`, `--count`, `--seed`, `--dry-run`.

Daten liegen in `~/.cs2_rewards/` (Ledger `ledger.json` und Cache). Ein anderer Ort lässt sich mit `REWARD_HOME` festlegen.

### Erster Test mit CSFloat-Key

```bash
reward claim S "Test" --provider csfloat --dry-run
```

Erscheinen Vorschläge mit Float-Werten und `csfloat.com/item/...`-Links, passt alles. Bei einer Fehlermeldung bitte die Ausgabe an Claude schicken, dann wird der Parser angepasst. Die Feldnamen sind bisher nur aus der Doku übernommen und noch nicht mit einem echten Key getestet.

## Entwicklung

```bash
pip install -e ".[dev]"
pytest
```

## Später möglich

- Wunschliste mit konkreten Skins, die geprüft wird, sobald einer ins Budget passt
- Sparen: mehrere offene Belohnungen zu einem größeren Budget zusammenlegen (z. B. 3× S = 1× M)
