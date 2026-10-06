# Data sources

## Required (cable pages)

| Upload | Typical name | Used for |
|--------|--------------|----------|
| Status list | Progressliste | Pull status, stops, partial meters, `verlegt` |
| Cable list | CaTra / Gesamtliste (Kabelziehliste) | Pathway (`Pfad`), devices, length, type |

Joined on normalized cable ID (`join_key`). Unmatched IDs and field conflicts appear on **Hibák**.

## Optional

| Upload | Used for |
|--------|----------|
| Workforce hours Excel | Workforce page; weekly hours on Progress (`H` = holiday) |
| Areas / Helység Excel | Areas page — columns: name, deck, ID, cable trays, penetrations |

## Local cache

Parsed data is stored in SQLite under `data/cables.db` so re-uploads are not needed every session. Use the sidebar **Clear …** buttons to reset.

## German

See [data-sources.de.md](data-sources.de.md).
