"""
seed.py — erzeugt Fake-Daten für mini-contacts.

Dieses Skript kommt ohne Zusatzpakete aus (nur Python-Standardbibliothek),
damit es auf jedem Rechner sofort läuft. Für größere oder realistischere
Datenmengen lohnen sich spezialisierte Werkzeuge — siehe docs/06_fake_daten.md:

  * Mockaroo (https://www.mockaroo.com) — Fake-Daten im Browser konfigurieren,
    Export als CSV, SQL oder JSON (Stand 08/2026).
  * Faker (https://faker.readthedocs.io) — Python-Paket mit Locale de_DE:
    `pip install faker`, dann fake.name(), fake.address(), fake.email().
  * KI-Assistenten (Claude, ChatGPT, ...) — Schema hingeben und INSERT-
    Statements generieren lassen; Ergebnis immer gegen die CHECK- und
    UNIQUE-Constraints laufen lassen.

Aufruf:
    python seed.py            # legt contacts.db an und füllt sie
    python seed.py --fresh    # löscht eine vorhandene contacts.db vorher
"""
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

BASIS = Path(__file__).parent
DB_PFAD = BASIS / "contacts.db"
SCHEMA = BASIS / "db" / "schema.sql"

random.seed(42)  # reproduzierbar: jeder Lauf erzeugt dieselben Daten

VORNAMEN = [
    "Anna", "Ben", "Clara", "David", "Elif", "Felix", "Greta", "Hannes",
    "Ida", "Jonas", "Katharina", "Leon", "Mia", "Noah", "Olivia", "Paul",
    "Ronja", "Samuel", "Theresa", "Umut", "Viktoria", "Willi", "Xenia",
    "Yusuf", "Zoe", "Lena", "Moritz", "Sofia", "Tim", "Carla",
]
NACHNAMEN = [
    "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner",
    "Becker", "Schulz", "Hoffmann", "Koch", "Bauer", "Richter", "Klein",
    "Wolf", "Schröder", "Neumann", "Schwarz", "Zimmermann", "Braun",
    "Krüger", "Hofmann", "Hartmann", "Lange", "Werner", "Krause", "Lehmann",
]
STRASSEN = [
    "Hauptstraße", "Bahnhofstraße", "Gartenweg", "Lindenallee", "Ringstraße",
    "Schulstraße", "Am Sonnenhang", "Mühlweg", "Kirchplatz", "Rosenweg",
    "Domstraße", "Sanderring", "Frankenallee", "Talavera", "Mainkai",
]
# PLZ -> Ort gehört fachlich zusammen (transitive Abhängigkeit, siehe
# docs/03_normalisierung.md) — deshalb hier als Paare gepflegt.
PLZ_ORTE = [
    ("97070", "Würzburg"), ("97080", "Würzburg"), ("97082", "Würzburg"),
    ("97318", "Kitzingen"), ("97421", "Schweinfurt"), ("63739", "Aschaffenburg"),
    ("90402", "Nürnberg"), ("80331", "München"), ("60311", "Frankfurt am Main"),
    ("10115", "Berlin"), ("20095", "Hamburg"), ("50667", "Köln"),
]
GRUPPEN = [
    ("Familie", "#2E7D32"), ("Arbeit", "#003E6E"), ("Studium", "#1F7F8C"),
    ("Verein", "#ED7004"), ("Nachbarschaft", "#8A5A9E"),
]
MAIL_DOMAINS = ["example.org", "example.com", "mail.example.de"]
NOTIZEN = [
    None, None, None,
    "Kennt sich mit SQL aus.",
    "Bringt zum Grillabend immer Salat mit.",
    "Erreichbar am besten vormittags.",
    "Alte Studienbekanntschaft.",
    "Nur noch selten Kontakt.",
]


def zufalls_geburtstag() -> str:
    start = date(1960, 1, 1)
    tage = (date(2007, 12, 31) - start).days
    return (start + timedelta(days=random.randrange(tage))).isoformat()


def telefonnummer(prefix: str) -> str:
    return f"{prefix} {random.randrange(100, 999)} {random.randrange(10000, 99999)}"


def main() -> None:
    if "--fresh" in sys.argv and DB_PFAD.exists():
        DB_PFAD.unlink()
        print(f"Vorhandene {DB_PFAD.name} gelöscht.")

    con = sqlite3.connect(DB_PFAD)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))

    if con.execute("SELECT COUNT(*) FROM kontakt").fetchone()[0] > 0:
        print("contacts.db enthält bereits Daten — nichts zu tun "
              "(mit --fresh neu aufbauen).")
        con.close()
        return

    cur = con.cursor()
    gruppen_ids = []
    for name, farbe in GRUPPEN:
        cur.execute("INSERT INTO gruppe (name, farbe) VALUES (?, ?) "
                    "ON CONFLICT(name) DO NOTHING",
                    (name, farbe))
        # Gruppen überleben das Löschen aller Kontakte. Vorhandene Gruppen
        # samt Farbe wiederverwenden, eigene Gruppen nicht verändern.
        gruppen_ids.append(cur.execute("SELECT gruppe_id FROM gruppe WHERE name = ?",
                                      (name,)).fetchone()[0])

    paare = {(v, n) for v in VORNAMEN for n in NACHNAMEN}
    for vorname, nachname in random.sample(sorted(paare), 48):
        cur.execute(
            "INSERT INTO kontakt (vorname, nachname, geburtstag, notiz) "
            "VALUES (?, ?, ?, ?)",
            (vorname, nachname, zufalls_geburtstag(), random.choice(NOTIZEN)))
        kid = cur.lastrowid

        mail = (f"{vorname}.{nachname}".lower()
                .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
                .replace("ß", "ss") + "@" + random.choice(MAIL_DOMAINS))
        cur.execute("INSERT INTO kanal (kontakt_id, typ, wert) VALUES (?, ?, ?)",
                    (kid, "email", mail))
        cur.execute("INSERT INTO kanal (kontakt_id, typ, wert) VALUES (?, ?, ?)",
                    (kid, "mobil", telefonnummer("+49 17")))
        if random.random() < 0.4:
            cur.execute("INSERT INTO kanal (kontakt_id, typ, wert) "
                        "VALUES (?, ?, ?)",
                        (kid, "festnetz", telefonnummer("+49 931")))

        for typ in random.sample(["privat", "arbeit"],
                                 k=random.choice([1, 1, 1, 2])):
            plz, ort = random.choice(PLZ_ORTE)
            cur.execute(
                "INSERT INTO adresse (kontakt_id, typ, strasse, hausnummer, "
                "plz, ort) VALUES (?, ?, ?, ?, ?, ?)",
                (kid, typ, random.choice(STRASSEN),
                 str(random.randrange(1, 120)), plz, ort))

        for gid in random.sample(gruppen_ids, k=random.choice([0, 1, 1, 2])):
            cur.execute("INSERT INTO kontakt_gruppe (kontakt_id, gruppe_id) "
                        "VALUES (?, ?)", (kid, gid))

    con.commit()
    n = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
         for t in ("kontakt", "kanal", "adresse", "gruppe", "kontakt_gruppe")}
    con.close()
    print(f"contacts.db gefüllt: {n['kontakt']} Kontakte, {n['kanal']} Kanäle, "
          f"{n['adresse']} Adressen, {n['gruppe']} Gruppen, "
          f"{n['kontakt_gruppe']} Gruppenzuordnungen.")


if __name__ == "__main__":
    main()
