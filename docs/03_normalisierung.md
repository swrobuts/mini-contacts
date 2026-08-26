# Schritt 3 — Normalisierung: von der flachen Liste zur 3NF

> **Lernziel:** Normalisierung ist kein Selbstzweck, sondern beseitigt
> konkrete Probleme: Redundanz und die daraus folgenden Anomalien beim
> Einfügen, Ändern und Löschen.

## 3.0 Ausgangspunkt: die "Excel-Tabelle"

So sähe die Kontaktverwaltung aus, wenn man sie naiv als eine einzige
Tabelle anlegt — wie eine Tabellenkalkulation:

| name | telefon | adresse | gruppen |
|------|---------|---------|---------|
| Anna Müller | +49 171 111, +49 931 222 | Hauptstr. 5, 97070 Würzburg | Familie, Verein |
| Ben Bauer | +49 172 333 | Mainkai 53, 97082 Würzburg | Arbeit |
| Anna Müller | +49 171 111 | Gartenweg 2, 97318 Kitzingen | Familie |

Die Probleme dieser Tabelle:

* **Mehrere Werte pro Zelle** (`telefon`, `gruppen`) — nicht durchsuchbar,
  nicht sortierbar, nicht einzeln löschbar.
* **Zwei Zeilen "Anna Müller"** — ist das dieselbe Person mit zwei Adressen
  oder sind es zwei Personen? Die Tabelle kann es nicht sagen.
* **Änderungsanomalie:** Ändert sich Annas Nummer, muss sie in mehreren
  Zeilen geändert werden — vergisst man eine, sind die Daten widersprüchlich.
* **Löschanomalie:** Löscht man Ben, verschwindet mit ihm das Wissen,
  dass es die Gruppe "Arbeit" gibt.
* **Einfügeanomalie:** Eine neue Gruppe ohne Mitglied kann man gar nicht
  erfassen.

## 3.1 Erste Normalform (1NF): nur atomare Werte

**Regel:** Jedes Attribut enthält genau einen Wert — keine Listen, keine
Wiederholungsgruppen.

Die Listen in `telefon` und `gruppen` werden aufgelöst; jeder Wert bekommt
eine eigene Zeile. Außerdem zerlegen wir zusammengesetzte Werte
(`name` → `vorname`, `nachname`; `adresse` → `strasse`, `plz`, `ort`)
und führen `kontakt_id` als eindeutigen Schlüssel ein:

| kontakt_id | vorname | nachname | kanal_typ | kanal_wert | strasse | plz | ort | gruppe |
|------------|---------|----------|-----------|------------|---------|-----|-----|--------|
| 1 | Anna | Müller | mobil | +49 171 111 | Hauptstr. 5 | 97070 | Würzburg | Familie |
| 1 | Anna | Müller | festnetz | +49 931 222 | Hauptstr. 5 | 97070 | Würzburg | Familie |
| 1 | Anna | Müller | mobil | +49 171 111 | Hauptstr. 5 | 97070 | Würzburg | Verein |
| 2 | Ben | Bauer | mobil | +49 172 333 | Mainkai 53 | 97082 | Würzburg | Arbeit |

Atomar — aber die Redundanz ist **schlimmer** geworden: Annas Name steht
jetzt dreimal da. Das ist normal: 1NF macht die Struktur sauber, die
Redundanz beseitigen erst 2NF und 3NF.

## 3.2 Zweite Normalform (2NF): keine partiellen Abhängigkeiten

**Regel:** 1NF, und jedes Nicht-Schlüssel-Attribut hängt vom *ganzen*
Schlüssel ab — nicht nur von einem Teil.

Der Schlüssel der 1NF-Tabelle ist zusammengesetzt (mindestens
`kontakt_id + kanal_wert + gruppe`). Aber `vorname` und `nachname` hängen
nur von `kontakt_id` ab, `kanal_typ` nur von `kontakt_id + kanal_wert`,
`gruppe` unabhängig vom Kanal. Diese *partiellen Abhängigkeiten* zerlegen
wir in eigene Tabellen:

* **kontakt** (kontakt_id, vorname, nachname, geburtstag, notiz)
* **kanal** (kanal_id, kontakt_id, typ, wert)
* **adresse** (adresse_id, kontakt_id, typ, strasse, hausnummer, plz, ort)
* **gruppe** (gruppe_id, name) und **kontakt_gruppe** (kontakt_id, gruppe_id)

Jetzt steht Annas Name genau einmal in der Datenbank — egal wie viele
Nummern, Adressen und Gruppen sie hat.

## 3.3 Dritte Normalform (3NF): keine transitiven Abhängigkeiten

**Regel:** 2NF, und kein Nicht-Schlüssel-Attribut hängt von einem *anderen
Nicht-Schlüssel-Attribut* ab.

In `adresse` steckt der Klassiker: **plz → ort**. Der Ort hängt nicht vom
Schlüssel `adresse_id` direkt ab, sondern transitiv über die Postleitzahl:
`adresse_id → plz → ort`. Streng nach 3NF müsste man zerlegen:

* **adresse** (adresse_id, kontakt_id, typ, strasse, hausnummer, plz)
* **ort** (plz, ort)

### Die Entwurfsentscheidung — und warum wir sie anders treffen

Wir **behalten `ort` bewusst in der Adresstabelle**. Warum?

| strenge 3NF (eigene Ort-Tabelle) | unsere pragmatische Lösung |
|----------------------------------|----------------------------|
| Ortsnamen zentral, keine Tippfehler-Varianten | ein JOIN weniger bei jeder Abfrage |
| Voraussetzung: gepflegtes PLZ-Verzeichnis (~13 000 Einträge) | keine Stammdatenpflege nötig |
| korrekt auch für PLZ mit mehreren Orten? Nein — real ist plz → ort gar nicht immer eindeutig! | dieselbe Realität, einfacher abgebildet |

Die Lektion: **Normalisierung ist ein Werkzeug zum Erkennen von Redundanz —
nicht jede erkannte Redundanz muss beseitigt werden.** Wichtig ist, die
Abweichung *bewusst* zu treffen und zu dokumentieren (siehe Kommentar in
[db/schema.sql](../db/schema.sql)). In einem Adressverzeichnis mit Millionen
Einträgen fiele die Entscheidung anders aus.

## 3.4 Ergebnis

Fünf Tabellen, jede beschreibt genau eine Sache, jeder Fakt steht genau
einmal in der Datenbank:

```mermaid
flowchart LR
    UNF["1 flache Tabelle\nListen in Zellen,\nRedundanz, Anomalien"] -->|1NF: atomar| N1["1 breite Tabelle\natomar, aber\nredundant"]
    N1 -->|2NF: partielle\nAbhängigkeiten raus| N2["5 Tabellen\njeder Fakt\neinmal"]
    N2 -->|3NF: transitive\nAbhängigkeiten prüfen| N3["5 Tabellen +\ndokumentierte\nEntscheidung plz→ort"]
    style N3 fill:#2E7D32,color:#fff
```

**Weiter:** [Schritt 4 — Relationales Modell](04_relationales_modell.md)
