# Schätzsystem (Areas) — Deutsch

Dieses Dokument beschreibt, wie die Seite **Areas** Restarbeit, Personenstunden und die voraussichtliche **Kalenderwoche (KW)** berechnet. Umsetzung: `src/areas.py`, Oberfläche: `views/areas.py`.

## 1. Welche Daten werden benötigt?

| Datei | Inhalt |
|-------|--------|
| Progressliste + Gesamtliste | Kabel, Länge, `verlegt`, Segmente, **Pfad** |
| Helység adatok (Areas) | Räume: Name, Deck, Kabeltrassen, Durchführungen (Penetrations) |

Ein Kabel gehört zu einem Raum, wenn sein **Pfad** mindestens einen Punkt aus den Trassen **oder** Durchführungen dieses Raums enthält.

## 2. Rollen eines Kabels im Raum

| Rolle | Bedeutung |
|-------|-----------|
| **Through** (durchlaufend) | Pfad trifft den Raum, A-/E-Endpunkt liegt **nicht** in der Raumliste |
| **Terminate** (endet) | Punkt A oder E liegt in der Raumliste |
| **Stop** | Aktuelles Gestoppt-**Endsegment** liegt in der Raumliste |

Stop kann zusammen mit Through/Terminate vorkommen.

**Verlegt-%** im Raum = Anteil der berührenden Kabel mit `verlegt`-Datum (Stückzahl, nicht Meter).

## 3. Restmeter pro Kabel (für die Stundenrechnung)

| Zustand | Restmeter in diesem Raum |
|---------|---------------------------|
| Vollständig verlegt (`verlegt`) | **0 m** |
| Noch nicht gestartet | **gesamte Kabellänge** (`Length_m`) |
| Teilgezogen | Meter vom aktuellen Halt (letztes Endsegment) **bis** zum Ziel im Raum: letzter Raumpunkt (durchlaufend) bzw. Endpunkt im Raum (terminate). Liegt die Zugfront **bereits hinter** dem Raum → **0 m** |

Dünne und dicke Restmeter werden getrennt summiert (Dicke ≥ 16 mm² = Thick).

## 4. Personenstunden (Arbeitsaufwand)

Standardgeschwindigkeiten (änderbar in der Planning-Leiste):

| Parameter | Default |
|-----------|---------|
| Dünne Kabel | **20 m / Stunde** (eine Person) |
| Dicke Kabel | **3 m / Stunde** |
| Stütze installieren | **5 Stunden** pro noch nicht abgehakter Stütze |

Formel:

```text
Personenstunden =
    (Restmeter_dünn / Pace_dünn)
  + (Restmeter_dick / Pace_dick)
  + (Anzahl_nicht_installierte_Stützen × Stunden_pro_Stütze)
```

**Stützen** im Raum = Einträge in Trassen/Durchführungen, die EDV/EDH enthalten.  
Abgehakte („installed“) Stützen zählen **nicht** mehr in die Stunden.  
Zusätzlich zeigt die App je Stütze den **Kabel-Fortschritt %** (100 %, wenn alle betreffenden Kabel verlegt sind bzw. die Zugfront die Stütze passiert hat).

## 5. Kapazität der Mannschaft

Eingaben (gespeichert):

| Eingabe | Default | Bedeutung |
|---------|---------|-----------|
| Cable pullers | 1 | Anzahl Kabelzieher (gemeinsamer Pool) |
| Hours / puller / week | **56** | Stunden **pro Zieher und Woche** |
| Max pullers / room | **5** | Max. Zieher gleichzeitig in einem Raum |
| As-of date | heute | Start der Terminrechnung |

```text
Wochenkapazität (ein Raum mit crew Ziehern) = crew × Stunden_pro_Woche
Tageskapazität (Mo–Fr)                     = Wochenkapazität / 5
```

## 6. Termin eines einzelnen Raums (ohne Parallelplanung)

```text
Arbeitstage = Aufrunden( Personenstunden / Tageskapazität )
Enddatum    = As-of-Datum um so viele Werktage (Mo–Fr) weiterzählen
KW-Label    = KW{ww} {yyyy}  (ISO-Kalenderwoche des Enddatums)
```

Samstag/Sonntag werden übersprungen. Bei 0 Stunden: Enddatum = As-of, KW = aktuelle Woche.

**Beispiel:** 112 Personenstunden, 2 Zieher × 56 h/Woche → Wochenkapazität 112 h → Tageskapazität 22,4 h → **5 Arbeitstage**. Start Montag → fertig Freitag derselben KW.

## 7. Parallele Raumplanung (Pool-Scheduler)

Mehrere Räume teilen sich denselben Zieher-Pool:

1. Räume werden nach **Priorität** sortiert (niedrigere Zahl = früher).
2. Ein Raum erhält bis zu `max_per_room` Zieher aus dem freien Pool (mindestens 1, solange frei).
3. Fertiggestellte Räume geben ihre Zieher frei; der nächste wartende Raum startet am **folgenden Werktag**.
4. Pro Raum erscheinen Start-/Enddatum, zugewiesene Crew, Warteschlangenrang und **KW**.

Die Gesamt-Zeile „All areas“ nutzt die Summe der Personenstunden und dieselbe Mannschaftslogik (parallel geplant).

## 8. Blocking (Sperren)

Man kann markieren:

- einen ganzen **Raum**, oder  
- eine **Trasse**, oder  
- eine **Durchführung**.

**Betroffene andere Räume** = Räume, die mindestens ein gemeinsames Kabel mit der gesperrten Einheit haben (Pfad-Schnittmenge). So sieht man, was eine Sperre blockiert.

## 9. Was die Schätzung nicht ist

- Keine automatische Übergabe-KW aus der Excel-Spalte „Handover KW“ (die App rechnet die KW selbst).
- Keine Berücksichtigung von Krankheit, Materialengpässen oder Parallelität *innerhalb* eines Raums jenseits von `max_per_room`.
- „Nicht gestartet → volle Länge“ ist bewusst konservativ (gesamtes Kabel, nicht nur der Raumabschnitt).

## 10. Wo einstellen?

Seite **Areas** → Leiste **Planning**: Pace, Stützenstunden, Zieher, Max/Raum, Wochenstunden, Datum.  
Stützen abhaken und Blocking im Raum-Detail.
