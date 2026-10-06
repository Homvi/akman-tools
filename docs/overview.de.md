# So funktioniert das Programm (Überblick)

## Zweck

Die App unterstützt Planung und Nachverfolgung der **Kabelverlegung** vor Ort. Sie verknüpft eine Statusliste (**Progressliste**) mit einer Kabelliste (**CaTra / Gesamtliste**), bietet Filter, Exporte, Fortschrittsdiagramme, raumbezogene Planung (**Areas**), Personalauswertungen und Datenqualitätsprüfungen (**Hibák**).

## Datenfluss

```text
Progressliste.xlsx  ──┐
                      ├── Join über Kabel-ID (join_key) ──► verbundene Kabelltabelle
Gesamtliste.xlsx   ──┘                                           │
                                                                 ▼
Helység adatok.xlsx (optional) ──► Seite Areas (Räume / Trassen / Durchführungen)
Workforce.xlsx (optional)      ──► Workforce + wöchentliche Progress-Stunden
```

1. Dateien in der **Seitenleiste** (Data files) hochladen.
2. Die App parst Excel, joinet Kabel und speichert lokal unter `data/` (SQLite).
3. Alle Seiten nutzen dieselbe Tabelle (plus optional Areas / Workforce).
4. Gemeinsame **Filter** gelten seitenübergreifend.

## Kabelstatus

- IDs: `5012.1` und `5012,1` gelten als gleich.
- **Verlegt** = echtes `verlegt`-Datum.
- **Teilgezogen** = Start-/Endsegment vorhanden, kein `verlegt`.
- **Nicht gestartet** = keine Zugaktivität.
- **Dicke**: ≥ 16 mm² → Thick (dick); sonst Thin (dünn).

## Schätzung / Termine

Die detaillierte Erklärung des **Schätz- und KW-Systems** (Meters, Stunden, Zieher, Kalenderwoche) steht auf Deutsch hier:

→ **[estimation.de.md](estimation.de.md)**

Weitere Themen: [pages.de.md](pages.de.md), [data-sources.de.md](data-sources.de.md).
