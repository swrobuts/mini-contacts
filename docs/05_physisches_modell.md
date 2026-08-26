# Schritt 5 — Physischer Entwurf: SQLite

> **Lernziel:** Das relationale Modell wird in konkretes SQL für ein
> konkretes Datenbanksystem übersetzt — mit dessen Eigenheiten.

## 5.1 Warum SQLite?

| | Datenbankserver (PostgreSQL, MySQL, SQL Server) | SQLite |
|--|--------------------------------------------------|--------|
| Betrieb | eigener Serverprozess, Netzwerk, Benutzerverwaltung | **eine Datei** (`contacts.db`), läuft im Prozess der Anwendung |
| Installation | Server installieren und konfigurieren | in Python eingebaut (`import sqlite3`) |
| Mehrbenutzer | viele gleichzeitige Schreiber | ein Schreiber zur Zeit — für lokale Apps völlig ausreichend |
| Einsatzgebiet | zentrale Unternehmensdaten | lokale Apps, Mobile (iOS/Android), Browser, Embedded |

SQLite ist die [meistverbreitete Datenbank der Welt](https://www.sqlite.org/mostdeployed.html) —
sie steckt in jedem Smartphone, Browser und in unzähligen Apps. Für eine
lokale Kontaktverwaltung ist sie genau richtig; für das
Vorlesungsverständnis ist wichtig: **SQL, Schlüssel und Normalformen sind
identisch zu den "großen" Systemen.**

## 5.2 SQLite-Eigenheiten, die man kennen muss

1. **Dynamische Typisierung.** SQLite kennt nur die Speicherklassen
   `INTEGER`, `REAL`, `TEXT`, `BLOB`, `NULL`. Typangaben wie `VARCHAR(50)`
   werden zu Affinitäten gemappt, aber nicht erzwungen (im
   Standard-Modus; seit SQLite 3.37 gibt es `STRICT`-Tabellen).
2. **Kein eigener Datumstyp.** Datumsangaben speichert man als `TEXT` im
   ISO-8601-Format (`'2007-05-14'`) — das sortiert und vergleicht korrekt.
3. **`INTEGER PRIMARY KEY`** ist der Alias für die interne `rowid` und
   zählt automatisch hoch; `AUTOINCREMENT` verhindert zusätzlich die
   Wiederverwendung gelöschter IDs.
4. **Fremdschlüssel sind ausschaltbar — und standardmäßig aus!**
   Aus Kompatibilitätsgründen prüft SQLite Fremdschlüssel nur, wenn je
   Verbindung `PRAGMA foreign_keys = ON` gesetzt wird. Der klassische
   Stolperstein: Ohne das Pragma sind `REFERENCES` nur Dokumentation.

## 5.3 Das Schema im Ausschnitt

Vollständig in [db/schema.sql](../db/schema.sql) — hier die Konstrukte,
auf die es ankommt:

```sql
CREATE TABLE kanal (
    kanal_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    kontakt_id  INTEGER NOT NULL
                REFERENCES kontakt(kontakt_id) ON DELETE CASCADE,
    typ         TEXT NOT NULL
                CHECK (typ IN ('mobil', 'festnetz', 'email', 'web')),
    wert        TEXT NOT NULL
);
```

* **`REFERENCES … ON DELETE CASCADE`** setzt Anforderung FA7 um: Löscht
  man einen Kontakt, löscht *die Datenbank* seine Kanäle, Adressen und
  Gruppenzuordnungen mit. Die Anwendung muss (und darf) sich nicht darum
  kümmern — Integrität ist Aufgabe der Datenbank.
* **`CHECK (typ IN (…))`** erzwingt den Wertebereich direkt im Schema —
  ein Enum auf Datenbankebene.
* **`UNIQUE`** auf `gruppe.name` verhindert doppelte Gruppen, egal was
  die Anwendung tut.

```sql
CREATE INDEX idx_kanal_kontakt ON kanal(kontakt_id);
```

* **Indexe auf Fremdschlüsseln:** Fast jede Abfrage der App sucht Kanäle
  und Adressen über `kontakt_id`. Der Index macht daraus einen direkten
  Zugriff statt eines Scans über die ganze Tabelle.

## 5.4 Ausprobieren auf der Kommandozeile

```bash
sqlite3 contacts.db
```

```sql
.tables                          -- welche Tabellen gibt es?
.schema kontakt                  -- wie ist kontakt definiert?
SELECT COUNT(*) FROM kontakt;    -- wie viele Kontakte?

-- JOIN über drei Tabellen: wer ist in welcher Gruppe?
SELECT k.nachname, k.vorname, g.name
  FROM kontakt k
  JOIN kontakt_gruppe kg ON kg.kontakt_id = k.kontakt_id
  JOIN gruppe g          ON g.gruppe_id   = kg.gruppe_id
 ORDER BY g.name, k.nachname;
```

**Weiter:** [Schritt 6 — Fake-Daten](06_fake_daten.md)
