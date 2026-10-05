# Recherche: Marktplätze, APIs und Steam-Einrichtung

Stand: Oktober 2026. Gebühren und Regeln ändern sich, vor größeren Käufen auf der jeweiligen Website nachsehen.

## Ergebnis in Kürze

- **CSFloat** bleibt erste Wahl. Die offizielle API kann Angebote suchen und filtern (Preis, Float, StatTrak, Sortierung) und braucht dafür einen API-Key.
  **Kaufen per API ist nicht offiziell dokumentiert.** Inoffizielle Wrapper nutzen zwar einen internen `POST /buy`-Endpunkt, das widerspricht aber unserer Regel „nur offizielle APIs“.
  → Ursprünglich öffnete das Tool nur den Angebotslink. **Auf Leonhards ausdrücklichen Wunsch gibt es jetzt den Geschenk-Modus**, der über den inoffiziellen Endpunkt selbst kauft (siehe unten).
- **Skinport** ist der Fallback ohne Key. Die öffentliche API liefert Preise direkt in EUR, aber nur den günstigsten Preis pro Skin (keine Einzelangebote, kein Float). Kaufen geht nur auf der Website.
- **DMarket** hätte als einzige eine offizielle Kauf-API. Die braucht aber signierte Requests (Ed25519-Schlüsselpaar) und ein Guthaben auf DMarket. Das wäre der offizielle Weg für den Geschenk-Modus gewesen. Leonhard hat sich aber für CSFloat entschieden.
- **Steam Community Market**: keine offizielle Kauf-API, rund 15 % Gebühr im Preis enthalten, Guthaben bleibt in Steam gebunden. Nur als Preisvergleich sinnvoll.

## CSFloat

| | |
|---|---|
| Doku | https://docs.csfloat.com |
| Key | csfloat.com → Profil → Tab „Developer“ |
| Auth | Header `Authorization: <API-KEY>` |
| Suche | `GET https://csfloat.com/api/v1/listings` |
| Wichtige Parameter | `limit` (max. 50), `sort_by` (`lowest_price`, `best_deal`, `highest_discount`, `most_recent`, …), `category` (0 = egal, 1 = normal, 2 = StatTrak, 3 = Souvenir), `min_price`/`max_price` **in US-Cent**, `min_float`/`max_float`, `def_index`, `paint_index`, `market_hash_name`, `type` (`buy_now`/`auction`) |
| Antwort | `{"data": [listing, …], "cursor": …}`; ein Listing hat `id`, `price` (US-Cent), `type`, `item.market_hash_name`, `item.float_value`, `item.is_stattrak`, `item.type` |
| Angebotslink | `https://csfloat.com/item/<listing-id>` |
| Rate-Limits | pro Endpunkt, nach IP und Account; Header `x-ratelimit-*` |
| Ohne Key | `403 {"message":"You need to be logged in to search listings"}` (aus diesem Projekt heraus getestet) |

Geprüft wurde das über die offizielle Doku (über Suchergebnisse, weil `docs.csfloat.com` aus der Build-Umgebung nicht erreichbar war), den Go-Wrapper `Bios-Marcel/csfloat_go` und einen echten Aufruf ohne Key. Der Parser akzeptiert sowohl `{"data": [...]}` als auch eine reine Liste.

**Mit Leonhards echtem Developer-Key (Oktober 2026) live bestätigt:**
- `GET /me` liefert tatsächlich `user.balance` und `user.pending_balance` in US-Cent, plus `know_your_customer` (`"uninitiated"` bei noch nicht verifizierten Konten), `has_api_key`, `withdraw_fee`, `fee`.
- `GET /listings` liefert `{"data": [...], "cursor": ...}`, ein Listing hat genau die Felder, die der Parser erwartet (`id`, `price`, `type`, `item.market_hash_name`, `item.float_value`, `item.is_stattrak`, `item.type`).
- `CSFloatProvider.search()` und `balance_usd_cents()` liefen gegen die echte API ohne Anpassung durch.
- Auth per API-Key geht nur über den Header `Authorization: <KEY>`. Das Session-Cookie der Website (`Cookie: session=<JWT>`) ist ein anderer, getrennter Auth-Weg und funktioniert nicht als `Authorization`-Header.

### Kaufen (inoffiziell, Geschenk-Modus)

- `POST https://csfloat.com/api/v1/listings/buy`, Header `Authorization: <API-KEY>`, Body `{"contract_ids": ["<listing-id>"], "total_price": <US-Cent>}`
- `total_price` muss zum Listing-Preis passen. Hat sich der Preis geändert, lehnt CSFloat ab, statt teurer zu kaufen.
- Quelle: `BuyRequestPayload` und `Buy()` in https://github.com/Bios-Marcel/csfloat_go (`csfloat.go`). Nicht in der offiziellen Doku.
- **Guthaben:** `GET https://csfloat.com/api/v1/me` liefert `user.balance` (verfügbar) und `user.pending_balance` (noch gesperrt), beides in US-Cent. Das Tool liest `balance` vor dem Kauf und versucht nur Angebote, die das Guthaben deckt.
- **Ablauf nach dem Kauf:** Der Preis wird sofort vom Guthaben abgezogen und liegt bei CSFloat als Treuhand. Der Trade steht auf `queued`, bis der Verkäufer ihn annimmt (`pending`). Der Verkäufer schickt dann ein Steam-Trade-Angebot an das Steam-Konto **des Käufer-Accounts**. Leonhard nimmt es an. Nach Ablauf des Steam-Trade-Schutzes ist der Trade `verified`, und der Verkäufer bekommt das Geld. Schickt der Verkäufer nicht oder wird der Trade nicht angenommen, endet er als `cancelled`/`failed`, und das Guthaben kommt zurück.
- **Für andere kaufen geht nicht:** Gekaufte Items gehen immer an das Steam-Konto, das mit dem kaufenden CSFloat-Account verknüpft ist. Laut AGB ist ein Account persönlich und darf nicht geteilt werden.
- Risiken: Der Endpunkt kann sich ändern, die Nutzung kann gegen die AGB verstoßen, und es ist nicht bestätigt, dass ein Developer-Key kaufen darf. Der erste echte Test sollte eine S-Belohnung sein.

### Einzahlen (Guthaben aufladen)

**Live mit Leonhards Key geprüft, nur lesend / ohne abgeschlossene Zahlung (Oktober 2026):**

- Zahlungsabwickler ist **Stripe**. Alle Einzahlungen laufen über Stripe Checkout.
- `GET /api/v1/deposit/methods?currency=eur` (Auth per Key oder Session-Cookie) liefert pro Methode `enabled`, `require_kyc`, `minimum_cents`, `maximum_cents`, `fee.fixed_cents`, `fee.decimal`, `exchange_rate`, `limit_cents_without_kyc`.
  - Für Leonhards Konto aktiv: `card` (USD, ab $5, 2,8 % + $0,30), `card_foreign` (EUR, gleiche Gebühr, CSFloat-eigener EUR/USD-Kurs statt EZB-Kurs), `crypto` (USDC/USDP, 1 %, **KYC-Pflicht**). SEPA/iDEAL/ACH erschienen für dieses Konto nicht, obwohl der Frontend-Code sie als Methoden kennt — vermutlich regions- oder kontoabhängig freigeschaltet.
  - Maximalbetrag ohne KYC: $2.000 bei Karte; Gesamt-Maximum $20.000.
- Einzahlung auslösen: `POST /api/v1/deposit/stripe` mit `{"method": ..., "amount": <US-Cent, AUCH BEI currency=eur>, "currency": ...}`. **Wichtig:** `amount` ist immer in US-Cent zu übergeben, auch wenn `currency` auf `eur` steht — die Umrechnung macht CSFloat/Stripe serverseitig. Antwort: `{"id": "<Stripe-Checkout-Session-ID>", "redirect": {"url": "..."}}`.
  - Leerer Request → `400 {"code":4,"message":"min amount is $5.00 USD"}`. Der Mindestbetrag wird serverseitig vor allem anderen geprüft.
  - Der Endpunkt drosselt sehr scharf (`429 too many requests` schon bei der zweiten Anfrage kurz danach). Niemals in einer Schleife aufrufen.
  - Eine echte Test-Session über `card_foreign`/1000 (= $10) ergab einen **Live-Modus**-Stripe-Checkout-Link (`cs_live_...`), keine Sandbox. Die Stripe-eigene Session-Vorschau zeigte: Rechnungsposten „Float Funds ($10.00)" + „Stripe Fee" $0,54, Gesamtbetrag 9,59 € für $10 Guthaben (≈ 7,6 % über dem reinen EZB-Kurswert). Erfolgs-Rücksprung: `https://csfloat.com/profile/deposit/processing?session_id=...&method=...&total=...`.
  - `GET /api/v1/deposit/stripe/sessions/{id}` meldet `status`/`payment_status` der Session (bei der Test-Session: `open`/`unpaid`, da nicht bezahlt).
  - `GET /api/v1/me/payments/pending-deposits` listet offene, noch nicht gutgeschriebene Einzahlungen (z. B. langsame Methoden wie ACH).
- **Nicht einsehbar / nur Vermutung:** Wie CSFloat serverseitig von Stripe erfährt, dass bezahlt wurde (vermutlich ein von CSFloat gehosteter, signierter Stripe-Webhook, z. B. `checkout.session.completed`), und wie dort doppelte Zustellungen oder Rückbuchungen behandelt werden. Das liegt auf CSFloats Backend und ist von außen nicht zu prüfen, ohne unautorisiert gegen deren Produktivsystem zu testen — das haben wir bewusst nicht gemacht.
- Frühere Annahme „SEPA/Krypto beide gängig, ~1–2,8 % Gebühr" war ungenau: Der Fixbetrag ($0,30) macht sich bei kleinen Beträgen stark bemerkbar, und der CSFloat-eigene EUR-Kurs liegt über dem EZB-Kurs.

Gebühren für Käufer: Der Preis im Listing ist der Kaufpreis. Für Einzahlungen auf das CSFloat-Guthaben fallen je nach Methode und Betrag real **deutlich mehr als 3 %** an (siehe Tabelle):

| Einzahlung | Gebühr (Karte, 2,8 % + $0,30) | effektiv |
|---|---|---|
| $5 (Minimum) | $0,44 | 8,8 % |
| $10 | $0,58 | 5,8 % |
| $20 | $0,86 | 4,3 % |
| $50 | $1,70 | 3,4 % |
| $100 | $3,10 | 3,1 % |

Der `FX_SAFETY_MARGIN` von 3 % im Tool deckt das nur bei Einzahlungen ab ca. $100 ab. Bei kleinen, häufigen Einzahlungen (passend zu den S/M-Belohnungen) reicht er nicht. Empfehlung: größere, seltenere Einzahlungen (z. B. $25–50 auf Vorrat) statt vieler kleiner, und/oder den Aufschlag erhöhen — Entscheidung liegt bei Leonhard.

Seriosität: großer, etablierter Marktplatz (früher CSGOFloat), Käuferschutz über Treuhand. Verkäufer bekommen ihr Geld wegen Steams Trade-Schutz erst nach 7 Tagen.

## Skinport

| | |
|---|---|
| Doku | https://docs.skinport.com |
| Endpunkt | `GET https://api.skinport.com/v1/items?app_id=730&currency=EUR&tradable=0` |
| Auth | keine |
| Besonderheit | Antwort **nur mit Brotli** (`Accept-Encoding: br`) |
| Limit | 8 Anfragen / 5 Minuten, Server-Cache 5 Minuten (das Tool cached lokal 5 Minuten) |
| Felder | `market_hash_name`, `min_price`, `quantity`, `item_page`, `market_page` (Kategorie im Pfad: `rifle`, `pistol`, `smg`, `heavy`, `knife`, `gloves`, `container`, `key`, `sticker`, `charm`, …) |
| Kaufen | nur auf der Website |

Live getestet: rund 21.600 Einträge, davon etwa 2.700 unter 0,50 €. Seriosität: großer EU-Marktplatz (Sitz in Deutschland), zahlt in EUR, Zahlung per Karte/PayPal/Klarna u. a.

## DMarket

- Doku: https://docs.dmarket.com/v1/swagger.html, Beispiele unter https://github.com/dmarket/dm-trading-tools
- Öffentlicher und privater Schlüssel, jede Anfrage mit Ed25519 signiert (`X-Api-Key`, `X-Sign-Date`, `X-Request-Sign`)
- Kaufen per API ist offiziell möglich, aber nur mit Guthaben auf DMarket
- Nicht umgesetzt: mehr Aufwand und mehr Risiko (ein Key, der Geld ausgeben kann) bei wenig Nutzen

## Steam: was Leonhard einrichten muss

1. **Steam Guard Mobile Authenticator** in der Steam-App aktivieren. Ohne Authenticator (oder wenn er erst kurz aktiv ist) werden Trades bis zu 15 Tage zurückgehalten.
2. **Trade-URL** kopieren: Steam → Inventar → Handelsangebote → „Wer kann mir Handelsangebote senden?“ → Handels-URL. Diese URL im CSFloat- bzw. Skinport-Profil eintragen.
3. **Inventar auf „öffentlich“** stellen (Profil → Privatsphäre), damit der Marktplatz die Zustellung prüfen kann.
4. **Trade-Schutz (seit Juli 2025):** Jedes per Trade erhaltene CS2-Item ist 7 Tage geschützt. In dieser Zeit kann es benutzt, aber nicht weitergehandelt werden, und der Trade kann rückgängig gemacht werden. Für Leonhard heißt das: Skin annehmen und spielen geht sofort. Weiterverkaufen oder -tauschen geht erst nach 7 Tagen.
5. Trade-Angebote **nur in der offiziellen Steam-App oder im Client** annehmen und vorher prüfen, dass er nur empfängt und nichts abgibt.

Das Tool speichert kein Steam-Passwort und keine Steam-Guard-Secrets und nimmt keine Trades automatisch an.

## Quellen

- CSFloat API: https://docs.csfloat.com
- CSFloat Go-Wrapper (Endpunktübersicht): https://pkg.go.dev/github.com/Bios-Marcel/csfloat_go
- Skinport API: https://docs.skinport.com, https://docs.skinport.com/items
- DMarket API: https://docs.dmarket.com/v1/swagger.html, https://support.dmarket.com/hc/en-us/articles/25123136369297-How-to-start-using-Trading-API
- Trade-Schutz: https://www.steamanalyst.com/guides/trade-holds-bans, https://swap.gg/blog/cs2-7-day-trade-lock-explained
- EZB-Referenzkurse: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml
- Live-Verifikation der Deposit-/Me-/Listings-Endpunkte: eigene Abfragen gegen `csfloat.com/api/v1` mit Leonhards Developer-Key, Oktober 2026 (nur lesend bzw. eine nicht abgeschlossene Test-Checkout-Session)
