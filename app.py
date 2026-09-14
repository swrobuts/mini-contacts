"""
app.py — mini-contacts: lokale Kontaktverwaltung auf SQLite.

Didaktisches Demo für die Vorlesung Datenbanken: eine kleine CRUD-Anwendung
(Create, Read, Update, Delete), die zu jedem Klick das tatsächlich
ausgeführte SQL anzeigt. Läuft auf Windows, macOS und Linux — die Datenbank
ist eine einzige Datei (contacts.db), ein Server wird nicht gebraucht.

Start:
    pip install flask
    python seed.py        # einmalig: Demo-Daten erzeugen
    python app.py         # läuft auf http://127.0.0.1:5050
"""
import sqlite3
from collections import deque
from pathlib import Path

from flask import Flask, abort, g, redirect, render_template, request, url_for

BASIS = Path(__file__).parent
DB_PFAD = BASIS / "contacts.db"
SCHEMA = BASIS / "db" / "schema.sql"

app = Flask(__name__)

# Die letzten ausgeführten SQL-Statements für das Log-Panel in der UI.
# Bewusst global und flüchtig: ein Lehr-Werkzeug, kein Audit-Log.
sql_log = deque(maxlen=12)

KANAL_TYPEN = ["mobil", "festnetz", "email", "web"]
ADRESS_TYPEN = ["privat", "arbeit", "sonstige"]


# ---------------------------------------------------------------- Datenbank
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        erste_nutzung = not DB_PFAD.exists()
        g.db = sqlite3.connect(DB_PFAD)
        g.db.row_factory = sqlite3.Row
        # LIKE ignoriert Groß-/Kleinschreibung nur für ASCII-Zeichen.
        g.db.create_function("casefold", 1, lambda wert: wert.casefold(),
                             deterministic=True)
        # SQLite prüft Fremdschlüssel nur, wenn das je Verbindung
        # eingeschaltet wird — der klassische SQLite-Stolperstein.
        g.db.execute("PRAGMA foreign_keys = ON")
        if erste_nutzung:
            g.db.executescript(SCHEMA.read_text(encoding="utf-8"))
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def q(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    """Führt SQL aus und protokolliert es lesbar für das Log-Panel."""
    db = get_db()
    statements = []
    # SQLite expandiert die Parameter selbst, einschließlich Apostrophen
    # und Fragezeichen in Werten. Nur erfolgreiche Aufrufe protokollieren.
    db.set_trace_callback(statements.append)
    try:
        cursor = db.execute(sql, params)
    finally:
        db.set_trace_callback(None)
    if any(isinstance(wert, str) and "\0" in wert for wert in params):
        # Der SQLite-Trace kürzt Text am NUL-Zeichen. Für diesen Sonderfall
        # SQL und Parameter getrennt und mit sichtbaren Escapezeichen zeigen.
        sql_log.appendleft(f"{sql}\n-- Parameter: {params!r}")
    elif statements:
        sql_log.appendleft(statements[-1])
    return cursor


def kontakt_pruefen(kontakt_id: int):
    kontakt = q("SELECT * FROM kontakt WHERE kontakt_id = ?",
                (kontakt_id,)).fetchone()
    if kontakt is None:
        abort(404, description="Dieser Kontakt existiert nicht mehr.")
    return kontakt


def kontakt_werte(form):
    return (form.get("vorname", "").strip(),
            form.get("nachname", "").strip(),
            form.get("geburtstag") or None,
            form.get("notiz", "").strip() or None)


@app.errorhandler(sqlite3.IntegrityError)
def integritaetsfehler(_exc):
    get_db().rollback()
    return render_template("fehler.html", sql_log=list(sql_log)), 400


# ------------------------------------------------------------------- Routen
@app.route("/")
def index():
    suche = request.args.get("q", "").strip()
    gruppe = request.args.get("gruppe", type=int)

    sql = """SELECT k.*,
                    (SELECT wert FROM kanal
                      WHERE kontakt_id = k.kontakt_id AND typ = 'email'
                      LIMIT 1) AS email
               FROM kontakt k"""
    params: list = []
    if gruppe:
        sql += """ JOIN kontakt_gruppe kg ON kg.kontakt_id = k.kontakt_id
                   AND kg.gruppe_id = ?"""
        params.append(gruppe)
    if suche:
        sql += " WHERE casefold(k.vorname) LIKE ? OR casefold(k.nachname) LIKE ?"
        params += [f"%{suche.casefold()}%", f"%{suche.casefold()}%"]
    sql += " ORDER BY k.nachname, k.vorname"

    kontakte = q(sql, tuple(params)).fetchall()
    gruppen_je_kontakt = {}
    for row in q("""SELECT kg.kontakt_id, g.name, g.farbe
                      FROM kontakt_gruppe kg
                      JOIN gruppe g ON g.gruppe_id = kg.gruppe_id
                     ORDER BY g.name""").fetchall():
        gruppen_je_kontakt.setdefault(row["kontakt_id"], []).append(row)

    gruppen = q("""SELECT g.*, COUNT(kg.kontakt_id) AS anzahl
                     FROM gruppe g
                     LEFT JOIN kontakt_gruppe kg ON kg.gruppe_id = g.gruppe_id
                    GROUP BY g.gruppe_id ORDER BY g.name""").fetchall()
    return render_template("index.html", kontakte=kontakte, gruppen=gruppen,
                           gruppen_je_kontakt=gruppen_je_kontakt,
                           suche=suche, aktive_gruppe=gruppe, sql_log=sql_log)


@app.route("/kontakt/neu", methods=["GET", "POST"])
def kontakt_neu():
    fehler = None
    if request.method == "POST":
        werte = kontakt_werte(request.form)
        if not werte[0] or not werte[1]:
            fehler = "Bitte gib einen Vornamen und einen Nachnamen ein."
        else:
            cur = q("INSERT INTO kontakt (vorname, nachname, geburtstag, notiz) "
                    "VALUES (?, ?, ?, ?)", werte)
            get_db().commit()
            return redirect(url_for("kontakt_bearbeiten", kontakt_id=cur.lastrowid))
    return render_template("form.html", kontakt=None, kanaele=[], adressen=[],
                           gruppen=[], zugeordnet=set(),
                           werte=request.form, fehler=fehler,
                           kanal_typen=KANAL_TYPEN, adress_typen=ADRESS_TYPEN,
                           sql_log=list(sql_log)), 422 if fehler else 200


@app.route("/kontakt/<int:kontakt_id>", methods=["GET", "POST"])
def kontakt_bearbeiten(kontakt_id: int):
    if request.method == "POST":
        kontakt = kontakt_pruefen(kontakt_id)
    else:
        kontakt = q("SELECT * FROM kontakt WHERE kontakt_id = ?",
                    (kontakt_id,)).fetchone()
        if kontakt is None:
            return redirect(url_for("index"))
    fehler = None
    if request.method == "POST":
        f = request.form
        werte = kontakt_werte(f)
        try:
            zugeordnet = {int(gid) for gid in f.getlist("gruppen")}
        except ValueError:
            abort(400, description="Ungültige Gruppenauswahl.")
        if not werte[0] or not werte[1]:
            fehler = "Bitte gib einen Vornamen und einen Nachnamen ein."
        else:
            q("UPDATE kontakt SET vorname = ?, nachname = ?, geburtstag = ?, "
              "notiz = ? WHERE kontakt_id = ?", (*werte, kontakt_id))
            # Gruppenzuordnung (N:M): alte Zuordnungen raus, angehakte rein.
            q("DELETE FROM kontakt_gruppe WHERE kontakt_id = ?", (kontakt_id,))
            for gid in sorted(zugeordnet):
                q("INSERT INTO kontakt_gruppe (kontakt_id, gruppe_id) "
                  "VALUES (?, ?)", (kontakt_id, gid))
            get_db().commit()
            return redirect(url_for("index"))
    kanaele = q("SELECT * FROM kanal WHERE kontakt_id = ? ORDER BY typ",
                (kontakt_id,)).fetchall()
    adressen = q("SELECT * FROM adresse WHERE kontakt_id = ? ORDER BY typ",
                 (kontakt_id,)).fetchall()
    gruppen = q("SELECT * FROM gruppe ORDER BY name").fetchall()
    if request.method == "GET":
        zugeordnet = {r["gruppe_id"] for r in
                      q("SELECT gruppe_id FROM kontakt_gruppe WHERE kontakt_id = ?",
                        (kontakt_id,)).fetchall()}
    return render_template("form.html", kontakt=kontakt, kanaele=kanaele,
                           adressen=adressen, gruppen=gruppen,
                           werte=request.form if fehler else dict(kontakt),
                           fehler=fehler,
                           zugeordnet=zugeordnet, kanal_typen=KANAL_TYPEN,
                           adress_typen=ADRESS_TYPEN, sql_log=list(sql_log)), 422 if fehler else 200


@app.route("/kontakt/<int:kontakt_id>/loeschen", methods=["POST"])
def kontakt_loeschen(kontakt_id: int):
    # ON DELETE CASCADE räumt Kanäle, Adressen und Gruppenzuordnungen
    # automatisch mit ab — das übernimmt die Datenbank, nicht die App.
    q("DELETE FROM kontakt WHERE kontakt_id = ?", (kontakt_id,))
    get_db().commit()
    return redirect(url_for("index"))


@app.route("/kontakt/<int:kontakt_id>/kanal", methods=["POST"])
def kanal_neu(kontakt_id: int):
    kontakt_pruefen(kontakt_id)
    f = request.form
    if f.get("wert", "").strip():
        q("INSERT INTO kanal (kontakt_id, typ, wert) VALUES (?, ?, ?)",
          (kontakt_id, f["typ"], f["wert"].strip()))
        get_db().commit()
    return redirect(url_for("kontakt_bearbeiten", kontakt_id=kontakt_id))


@app.route("/kanal/<int:kanal_id>/loeschen", methods=["POST"])
def kanal_loeschen(kanal_id: int):
    kid = request.form["kontakt_id"]
    q("DELETE FROM kanal WHERE kanal_id = ?", (kanal_id,))
    get_db().commit()
    return redirect(url_for("kontakt_bearbeiten", kontakt_id=kid))


@app.route("/kontakt/<int:kontakt_id>/adresse", methods=["POST"])
def adresse_neu(kontakt_id: int):
    kontakt_pruefen(kontakt_id)
    f = request.form
    if f.get("strasse", "").strip():
        q("INSERT INTO adresse (kontakt_id, typ, strasse, hausnummer, plz, "
          "ort) VALUES (?, ?, ?, ?, ?, ?)",
          (kontakt_id, f["typ"], f["strasse"].strip(),
           f.get("hausnummer", "").strip() or None,
           f["plz"].strip(), f["ort"].strip()))
        get_db().commit()
    return redirect(url_for("kontakt_bearbeiten", kontakt_id=kontakt_id))


@app.route("/adresse/<int:adresse_id>/loeschen", methods=["POST"])
def adresse_loeschen(adresse_id: int):
    kid = request.form["kontakt_id"]
    q("DELETE FROM adresse WHERE adresse_id = ?", (adresse_id,))
    get_db().commit()
    return redirect(url_for("kontakt_bearbeiten", kontakt_id=kid))


@app.route("/gruppe/neu", methods=["POST"])
def gruppe_neu():
    name = request.form.get("name", "").strip()
    if name:
        try:
            q("INSERT INTO gruppe (name, farbe) VALUES (?, ?)",
              (name, request.form.get("farbe", "#003E6E")))
            get_db().commit()
        except sqlite3.IntegrityError:
            get_db().rollback()  # UNIQUE(name) — Duplikate weist die DB ab
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Port 5000 ist auf macOS oft durch AirPlay belegt — daher 5050
    # als Standard, per Umgebungsvariable PORT übersteuerbar.
    import os
    app.run(debug=True, port=int(os.environ.get("PORT", 5050)))
