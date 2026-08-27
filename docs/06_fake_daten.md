# Schritt 6 — Fake-Daten: die Datenbank realistisch füllen

> **Lernziel:** Eine leere Datenbank kann man nicht testen und nicht
> vorführen. Testdaten generiert man — von Hand tippt sie niemand.

## 6.1 Unser Weg: seed.py (nur Standardbibliothek)

[seed.py](../seed.py) erzeugt 48 Kontakte mit Kanälen, Adressen und
Gruppenzuordnungen — ohne Zusatzpakete, damit es überall sofort läuft:

* Namen, Straßen und Gruppen aus kleinen Wortlisten, kombiniert per `random`
* `random.seed(42)` macht jeden Lauf **reproduzierbar** — wichtig, wenn
  alle im Kurs mit denselben Daten arbeiten sollen
* PLZ und Ort als **Paare** gepflegt (`("97070", "Würzburg")`) — sonst
  entstünden Adressen, die der transitiven Abhängigkeit plz → ort
  widersprechen ([Schritt 3](03_normalisierung.md))

```bash
python seed.py           # füllt contacts.db (falls leer)
python seed.py --fresh   # baut contacts.db komplett neu auf
```

## 6.2 Werkzeuge für größere oder realistischere Datenmengen

### Mockaroo (Browser, ohne Programmierung)

[mockaroo.com](https://www.mockaroo.com) (Stand 08/2026): Spalten und
Datentypen zusammenklicken ("First Name", "Email", "Street Address", …),
bis zu 1 000 Zeilen im Gratis-Plan, Export als **CSV, JSON oder direkt als
SQL-INSERTs**. Ideal, um schnell realistische Daten für ein gegebenes
Schema zu bekommen — inklusive Formeln und Wahrscheinlichkeiten
("20 % der Zellen leer").

### Faker (Python-Paket)

[Faker](https://faker.readthedocs.io) generiert lokalisierte Fake-Daten
programmatisch — mit `de_DE` klingen Namen und Adressen deutsch:

```python
from faker import Faker          # pip install faker
fake = Faker("de_DE")
fake.name()          # 'Dr. Ingeborg Hentschel'
fake.street_address()  # 'Birkensteige 3'
fake.email()         # 'ppaffrath@example.net'
```

Stärke: beliebige Mengen, direkt im eigenen Skript, viele Domänen
(IBANs, Firmennamen, Texte). Schwäche: PLZ und Ort passen nicht
zwingend zusammen — wer das braucht, pflegt wie in `seed.py` echte Paare.

### KI-Assistenten (Claude, ChatGPT, …)

Schema hingeben und Daten generieren lassen:

> *"Hier ist mein CREATE TABLE für `kontakt`, `kanal` und `adresse`.
> Erzeuge 30 realistische deutsche Beispieldatensätze als INSERT-Statements.
> Beachte die CHECK-Constraints und dass PLZ und Ort zusammenpassen."*

Stärken: versteht das Schema samt Constraints, erzeugt in sich stimmige
Daten ("Anna Müller" bekommt `anna.mueller@…`). Grenzen:

* **Immer gegen das echte Schema laufen lassen** — die Datenbank prüft
  CHECK, UNIQUE und Fremdschlüssel zuverlässiger als jedes Sprachmodell.
* Bei großen Mengen (tausende Zeilen) sind Mockaroo oder Faker schneller
  und billiger.

## 6.3 Grundregeln für Testdaten

1. **Keine echten Personendaten.** Niemals das eigene Adressbuch in ein
   Demo-Repo laden — Fake-Daten sind auch eine Datenschutzmaßnahme.
   (Deshalb enden alle E-Mail-Adressen hier auf `example.org` & Co. —
   Domains, die für genau diesen Zweck reserviert sind.)
2. **Constraints testen die Daten, Daten testen die Constraints.**
   Generierte Daten, die das Schema ablehnt, zeigen entweder einen Fehler
   im Generator — oder einen im Schema. Beides will man wissen.
3. **Reproduzierbarkeit** (fester Seed) schlägt Originalität: gleiche
   Daten bei allen erleichtern Lehre, Debugging und Vergleiche.

**Weiter:** [Schritt 7 — Architektur der Anwendung](07_architektur.md)
