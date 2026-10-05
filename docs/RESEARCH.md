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

Geprüft wurde das über die offizielle Doku (über Suchergebnisse, weil `docs.csfloat.com` aus der Build-Umgebung nicht erreichbar war), den Go-Wrapper `Bios-Marcel/csfloat_go` und einen echten Aufruf ohne Key. **Die Feldnamen der Antwort sind noch nicht mit einem echten Key bestätigt.** Der erste Live-Test bei Leonhard (siehe README) klärt das. Der Parser akzeptiert sowohl `{"data": [...]}` als auch eine reine Liste.

### Kaufen (inoffiziell, Geschenk-Modus)

- `POST https://csfloat.com/api/v1/listings/buy`, Header `Authorization: <API-KEY>`, Body `{"contract_ids": ["<listing-id>"], "total_price": <US-Cent>}`
- `total_price` muss zum Listing-Preis passen. Hat sich der Preis geändert, lehnt CSFloat ab, statt teurer zu kaufen.
- Quelle: `BuyRequestPayload` und `Buy()` in https://github.com/Bios-Marcel/csfloat_go (`csfloat.go`). Nicht in der offiziellen Doku.
- Risiken: Der Endpunkt kann sich ändern, die Nutzung kann gegen die AGB verstoßen, und es ist nicht bestätigt, dass ein Developer-Key kaufen darf. Der erste echte Test sollte eine S-Belohnung sein.

Gebühren für Käufer: Der Preis im Listing ist der Kaufpreis. Für Einzahlungen auf das CSFloat-Guthaben können je nach Zahlungsart Gebühren anfallen. Das Tool rechnet deshalb USD→EUR mit dem EZB-Tageskurs **plus 3 % Aufschlag**, damit das Euro-Limit sicher hält.

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
