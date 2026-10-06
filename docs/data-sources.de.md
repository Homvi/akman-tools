# Datenquellen

## Pflicht (Kabel-Seiten)

| Upload | Typischer Name | Inhalt |
|--------|----------------|--------|
| Statusliste | Progressliste | Zugstatus, Stopps, Teilmeter, `verlegt` |
| Kabelliste | CaTra / Gesamtliste (Kabelziehliste) | Pfad, Geräte, Länge, Typ |

Verknüpfung über normalisierte Kabel-ID. Abweichungen: Seite **Hibák**.

## Optional

| Upload | Verwendung |
|--------|------------|
| Workforce-Excel | Seite Workforce; Stunden in Progress (`H` = Feiertag) |
| Areas / Helység-Excel | Seite Areas — Name, Deck, ID, Trassen, Durchführungen |

## Lokaler Cache

Daten liegen unter `data/cables.db` (SQLite). Zurücksetzen über die Clear-Buttons in der Seitenleiste.

Schätzlogik: [estimation.de.md](estimation.de.md).
