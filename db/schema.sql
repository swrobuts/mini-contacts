-- ============================================================
-- mini-contacts — physisches Datenbankschema (SQLite)
--
-- Ergebnis des Entwurfswegs:
--   Miniwelt -> ER-Modell (Chen) -> Normalisierung (1NF-3NF)
--   -> relationales Modell -> dieses Schema
-- Details: docs/02_er_modell.md bis docs/05_physisches_modell.md
-- ============================================================

-- SQLite prüft Fremdschlüssel erst, wenn das Pragma je Verbindung
-- gesetzt ist. Die Anwendung setzt es bei jedem Connect (app.py).
PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Entität KONTAKT — die zentrale Entität der Miniwelt
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kontakt (
    kontakt_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    vorname      TEXT NOT NULL,
    nachname     TEXT NOT NULL,
    geburtstag   TEXT,                                  -- ISO 8601: 'YYYY-MM-DD'
    notiz        TEXT,
    angelegt_am  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- Entität ADRESSE — 1:N zu KONTAKT (ein Kontakt hat 0..n Adressen)
-- Bewusste Entwurfsentscheidung: plz -> ort ist eine transitive
-- Abhängigkeit (Verstoß gegen strenge 3NF). Wir behalten beide
-- Spalten hier, weil eine eigene Ort-Tabelle für diese Miniwelt
-- mehr Komplexität als Nutzen brächte. Siehe docs/03_normalisierung.md.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS adresse (
    adresse_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    kontakt_id  INTEGER NOT NULL
                REFERENCES kontakt(kontakt_id) ON DELETE CASCADE,
    typ         TEXT NOT NULL DEFAULT 'privat'
                CHECK (typ IN ('privat', 'arbeit', 'sonstige')),
    strasse     TEXT NOT NULL,
    hausnummer  TEXT,
    plz         TEXT NOT NULL,
    ort         TEXT NOT NULL
);

-- ------------------------------------------------------------
-- Entität KANAL — Telefonnummern, E-Mail-Adressen, Webseiten.
-- Ergebnis der 1NF: aus den Spalten telefon1/telefon2/email der
-- flachen Kontaktliste wird eine eigene Tabelle mit einer Zeile
-- je Wert.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kanal (
    kanal_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    kontakt_id  INTEGER NOT NULL
                REFERENCES kontakt(kontakt_id) ON DELETE CASCADE,
    typ         TEXT NOT NULL
                CHECK (typ IN ('mobil', 'festnetz', 'email', 'web')),
    wert        TEXT NOT NULL
);

-- ------------------------------------------------------------
-- Entität GRUPPE — N:M zu KONTAKT über die Koppeltabelle
-- kontakt_gruppe (ein Kontakt gehört zu 0..n Gruppen, eine
-- Gruppe enthält 0..n Kontakte).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gruppe (
    gruppe_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    farbe      TEXT NOT NULL DEFAULT '#003E6E'          -- Hex-Farbe für die UI
);

CREATE TABLE IF NOT EXISTS kontakt_gruppe (
    kontakt_id  INTEGER NOT NULL
                REFERENCES kontakt(kontakt_id) ON DELETE CASCADE,
    gruppe_id   INTEGER NOT NULL
                REFERENCES gruppe(gruppe_id) ON DELETE CASCADE,
    PRIMARY KEY (kontakt_id, gruppe_id)
);

-- Zugriffe laufen fast immer über kontakt_id — Indexe auf den
-- Fremdschlüsseln halten Detailansicht und Löschen schnell.
CREATE INDEX IF NOT EXISTS idx_adresse_kontakt ON adresse(kontakt_id);
CREATE INDEX IF NOT EXISTS idx_kanal_kontakt   ON kanal(kontakt_id);
