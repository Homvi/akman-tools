# How the program works (overview)

## Purpose

The app helps plan and track **cable pulling** on site. It joins a status list (**Progressliste**) with a cable list (**CaTra / Gesamtliste**), then offers filters, exports, progress charts, room-level planning (**Areas**), workforce views, and data-quality checks (**Hibák**).

## Main data flow

```text
Progressliste.xlsx  ──┐
                      ├── join on cable ID (join_key) ──► joined cable table
Gesamtliste.xlsx   ──┘                                         │
                                                               ▼
Helység adatok.xlsx (optional) ──► Areas page (rooms / trays / penetrations)
Workforce.xlsx (optional)      ──► Workforce + weekly Progress hours
```

1. Upload files in the **sidebar** (Data files).
2. The app parses Excel, joins cables, and caches results in local SQLite under `data/`.
3. Every page reads the same joined table (and optional Areas / Workforce data).
4. Shared **filters** (device, pull status, thickness, category, stop Stütze) apply across cable pages.

## Cable identity

- IDs are normalized so `5012.1` and `5012,1` match.
- **Pulled** = real `verlegt` date.
- **Partial** = has Start/End segment, no `verlegt`.
- **Not started** = no pull activity.
- **Thickness**: ≥ 16 mm² → Thick; otherwise Thin (special types count as Thin).

## What each major area of the app does

| Area | Role |
|------|------|
| Cable lists / Stütze / ID export | Find cables, copy IDs, export CaTra pull cards or Kurzliste |
| Progress | Daily / weekly pulled meters (KW) |
| Areas | Room progress, remaining work, **person-hours and KW ETA** — see [estimation.en.md](estimation.en.md) |
| Workforce | Headcount and hours from the workforce Excel |
| Hibák | Progressliste ↔ Gesamtliste mismatches |
| Calculator | Partial length along a pathway |

Details: [pages.en.md](pages.en.md), [data-sources.en.md](data-sources.en.md).
