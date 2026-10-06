# Estimation system (Areas) — English

How the **Areas** page computes remaining work, person-hours, and the target **calendar week (KW)**. Code: `src/areas.py`, UI: `views/areas.py`.

German version: [estimation.de.md](estimation.de.md).

## Inputs

| File | Role |
|------|------|
| Progressliste + Gesamtliste | Cables, length, `verlegt`, segments, **Pfad** |
| Helység adatok | Rooms: trays + penetrations |

A cable belongs to a room if its path hits any tray **or** penetration of that room.

## Cable roles in a room

- **Through** — hits room nodes; A/E endpoints outside the room set  
- **Terminate** — Point A or E is in the room set  
- **Stop** — current Gestoppt Endsegment is in the room set  

**Pulled %** = share of touching cables that have a `verlegt` date (count-based).

## Remaining meters

| State | Remaining m for that room |
|-------|---------------------------|
| Verlegt | 0 |
| Not started | full `Length_m` |
| Partial | meters from pull front (latest Endsegment) to clear the room (last room node or terminate endpoint); 0 if already past |

Thin and thick remaining meters are summed separately (≥ 16 mm² = Thick).

## Person-hours

Defaults (editable): thin **20 m/h**, thick **3 m/h**, Stütze **5 h** each (unchecked only).

```text
hours = thin_m/thin_pace + thick_m/thick_pace + unchecked_stuetzen × h_per_stuetze
```

## Crew & KW

- Weekly capacity = pullers × hours/week (default **56** per puller)  
- Daily capacity = weekly / 5 (Mon–Fri)  
- Workdays = ceil(hours / daily); end date skips weekends; label `KW{ww} {yyyy}`  

Multiple rooms share a puller pool with **max pullers / room** (default 5) and optional priority — see the German doc §7 for the parallel scheduler.

## Blocking

Block a room, tray, or penetration → list other rooms that share at least one cable with the blocked entity.
