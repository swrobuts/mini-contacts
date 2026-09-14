"""Regressionstests: python -m unittest discover -s tests -v"""
import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as contacts
import seed


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class ContactsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mini-contacts-test-")
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "contacts.db"
        self.override = patch.object(contacts, "DB_PFAD", self.db_path)
        self.override.start()
        self.addCleanup(self.override.stop)
        self.config = patch.dict(contacts.app.config, TESTING=True)
        self.config.start()
        self.addCleanup(self.config.stop)
        contacts.sql_log.clear()
        self.client = contacts.app.test_client()

    def query(self, sql, params=()):
        with contacts.app.app_context():
            db = contacts.get_db()
            result = db.execute(sql, params).fetchall()
            db.commit()
            return result

    def create(self, first="Anna", last="Muster", **extra):
        response = self.client.post("/kontakt/neu", data={"vorname": first, "nachname": last, **extra})
        self.assertEqual(response.status_code, 302)
        return int(response.location.rsplit("/", 1)[-1])

    def group(self, name="Studium"):
        self.client.post("/gruppe/neu", data={"name": name})
        return self.query("SELECT gruppe_id FROM gruppe WHERE name=?", (name,))[0][0]

    def run_seed(self):
        with patch.object(seed, "DB_PFAD", self.db_path), patch.object(sys, "argv", ["seed.py"]), contextlib.redirect_stdout(io.StringIO()):
            seed.main()

    def test_crud_filter_and_cascade(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/kontakt/neu").status_code, 200)
        kid = self.create()
        gid = self.group()
        self.client.post(f"/kontakt/{kid}", data={"vorname": "Anne", "nachname": "Muster", "gruppen": str(gid)})
        self.client.post(f"/kontakt/{kid}/kanal", data={"typ": "email", "wert": "anne@example.org"})
        self.client.post(f"/kontakt/{kid}/adresse", data={"typ": "privat", "strasse": "Testweg", "plz": "97070", "ort": "Würzburg"})
        html = self.client.get("/", query_string={"q": "Anne", "gruppe": gid}).get_data(as_text=True)
        self.assertIn("1 Kontakt gefunden", html)
        self.assertIn("anne@example.org", html)
        self.assertEqual(self.client.get(f"/kontakt/{kid}").status_code, 200)
        self.client.post(f"/kontakt/{kid}/loeschen")
        for table in ("kontakt", "kanal", "adresse", "kontakt_gruppe"):
            self.assertEqual(self.query(f"SELECT COUNT(*) FROM {table}")[0][0], 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM gruppe")[0][0], 1)

    def test_individual_channel_and_address_delete(self):
        kid = self.create()
        self.client.post(f"/kontakt/{kid}/kanal", data={"typ": "mobil", "wert": "000-test"})
        self.client.post(f"/kontakt/{kid}/adresse", data={"typ": "arbeit", "strasse": "Testweg", "plz": "97070", "ort": "Würzburg"})
        self.client.post("/kanal/1/loeschen", data={"kontakt_id": kid})
        self.client.post("/adresse/1/loeschen", data={"kontakt_id": kid})
        self.assertEqual(self.query("SELECT COUNT(*) FROM kanal")[0][0], 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM adresse")[0][0], 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM kontakt")[0][0], 1)

    def assert_safe_confirmation(self, kid, first, last):
        elements = Elements(self.client.get("/").get_data(as_text=True)).elements
        form = next(attrs for tag, attrs in elements if tag == "form" and attrs.get("action") == f"/kontakt/{kid}/loeschen")
        self.assertNotIn("onsubmit", form)
        self.assertEqual(form["data-confirm"], f"{first} {last} wirklich löschen?")
        self.assertFalse(any(key.startswith("on") for _, attrs in elements for key in attrs))
        scripts = [attrs for tag, attrs in elements if tag == "script"]
        self.assertEqual(scripts, [{"src": "/static/app.js", "defer": None}])

    def test_names_remain_data_on_create_edit_and_existing_rows(self):
        names = ["O'Connor", 'Muster "Test"', "Back\\slash", "Zeile\numbruch",
                 "'+(globalThis.marker=123)+'", '&quot;&#39;&amp;', '"><script>marker=123</script>']
        for name in names:
            with self.subTest(name=name):
                kid = self.create("Anna", name)
                self.assert_safe_confirmation(kid, "Anna", name)
                self.client.post(f"/kontakt/{kid}", data={"vorname": name, "nachname": "Muster"})
                self.assert_safe_confirmation(kid, name, "Muster")
                self.query("UPDATE kontakt SET nachname=? WHERE kontakt_id=?", (name, kid))
                self.assert_safe_confirmation(kid, name, name)

    def test_invalid_new_names_preserve_form(self):
        for first, last in [(" ", "Muster"), ("Anna", "\t"), ("", "")]:
            with self.subTest(first=first, last=last):
                response = self.client.post("/kontakt/neu", data={"vorname": first, "nachname": last, "notiz": "Nicht verlieren"})
                self.assertEqual(response.status_code, 422)
                self.assertIn("Bitte gib einen Vornamen", response.get_data(as_text=True))
                self.assertIn("Nicht verlieren", response.get_data(as_text=True))
        self.assertEqual(self.query("SELECT COUNT(*) FROM kontakt")[0][0], 0)

    def test_invalid_edit_keeps_database_and_form_group_selection(self):
        kid = self.create(notiz="Original")
        gid = self.group()
        response = self.client.post(f"/kontakt/{kid}", data={"vorname": " ", "nachname": "Muster", "notiz": "Entwurf", "gruppen": str(gid)})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Entwurf", response.get_data(as_text=True))
        form = next(attrs for tag, attrs in Elements(response.get_data(as_text=True)).elements if attrs.get("class") == "stack")
        self.assertEqual(form.get("data-unsaved"), "true")
        checkboxes = [attrs for tag, attrs in Elements(response.get_data(as_text=True)).elements if attrs.get("name") == "gruppen"]
        self.assertIn("checked", checkboxes[0])
        self.assertEqual(tuple(self.query("SELECT vorname, notiz FROM kontakt")[0]), ("Anna", "Original"))
        self.assertEqual(self.query("SELECT COUNT(*) FROM kontakt_gruppe")[0][0], 0)

    def test_trimmed_names_and_optional_fields(self):
        kid = self.create(" Anna ", " Muster ")
        self.assertEqual(tuple(self.query("SELECT vorname, nachname, geburtstag, notiz FROM kontakt WHERE kontakt_id=?", (kid,))[0]), ("Anna", "Muster", None, None))

    def test_log_uses_sqlite_literals(self):
        samples = [("Anna?", "Muster"), ("Anne", "O'Connor"), ("A'??", 'B"\\')]
        with contacts.app.app_context():
            db = contacts.get_db()
            for first, last in samples:
                with self.subTest(first=first, last=last):
                    quoted = db.execute("SELECT quote(?), quote(?)", (first, last)).fetchone()
                    contacts.q("INSERT INTO kontakt (vorname, nachname) VALUES (?, ?)", (first, last))
                    self.assertEqual(contacts.sql_log[0], f"INSERT INTO kontakt (vorname, nachname) VALUES ({quoted[0]}, {quoted[1]})")
                    self.assertEqual(tuple(db.execute("SELECT vorname, nachname FROM kontakt ORDER BY kontakt_id DESC LIMIT 1").fetchone()), (first, last))

    def test_log_null_and_number_and_failed_statement(self):
        with contacts.app.app_context():
            contacts.q("SELECT ?, ?", (None, 42)).fetchone()
            self.assertEqual(contacts.sql_log[0], "SELECT NULL, 42")
            with self.assertRaises(sqlite3.IntegrityError):
                contacts.q("INSERT INTO kontakt (vorname, nachname) VALUES (?, ?)", (None, "Muster"))
            self.assertEqual(contacts.sql_log[0], "SELECT NULL, 42")

    def test_log_keeps_nul_containing_parameters_visible(self):
        first, last = "A\x00B?'C", "D?E"
        kid = self.create(first, last)
        self.assertEqual(self.query("SELECT vorname FROM kontakt WHERE kontakt_id=?", (kid,))[0][0], first)
        self.assertIn("VALUES (?, ?, ?, ?)", contacts.sql_log[0])
        self.assertIn(repr((first, last, None, None)), contacts.sql_log[0])

    def test_unicode_search_and_group_filter(self):
        kid = self.create("Özlem", "Müller")
        self.create("Özlem", "Müller")
        gid = self.group()
        self.query("INSERT INTO kontakt_gruppe VALUES (?, ?)", (kid, gid))
        for term in ("müller", "MÜLLER", "özlem", "ÖZLEM"):
            with self.subTest(term=term):
                html = self.client.get("/", query_string={"q": term, "gruppe": gid}).get_data(as_text=True)
                self.assertIn("1 Kontakt gefunden", html)

    def test_special_characters_in_note_are_html_escaped(self):
        kid = self.create(notiz="<script>marker=123</script>")
        self.assertIn("&lt;script&gt;marker=123&lt;/script&gt;", self.client.get(f"/kontakt/{kid}").get_data(as_text=True))

    def test_seed_initial_and_repeat(self):
        self.run_seed()
        self.run_seed()
        self.assertEqual(self.query("SELECT COUNT(*) FROM kontakt")[0][0], 48)
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_seed_reuses_groups_after_all_contacts_deleted(self):
        self.run_seed()
        before = [tuple(row) for row in self.query("SELECT * FROM gruppe ORDER BY gruppe_id")]
        for row in self.query("SELECT kontakt_id FROM kontakt"):
            self.client.post(f"/kontakt/{row[0]}/loeschen")
        self.run_seed()
        self.assertEqual(self.query("SELECT COUNT(*) FROM kontakt")[0][0], 48)
        self.assertEqual([tuple(row) for row in self.query("SELECT * FROM gruppe ORDER BY gruppe_id")], before)
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_seed_preserves_custom_groups_and_existing_colors(self):
        self.query("INSERT INTO gruppe (name, farbe) VALUES (?, ?)", ("Studium", "#123456"))
        gid = self.group("Eigene Gruppe")
        self.run_seed()
        self.assertEqual(self.query("SELECT farbe FROM gruppe WHERE name='Studium'")[0][0], "#123456")
        self.assertEqual(self.query("SELECT COUNT(*) FROM gruppe")[0][0], 6)
        self.assertEqual(self.query("SELECT COUNT(*) FROM kontakt_gruppe WHERE gruppe_id=?", (gid,))[0][0], 0)

    def test_stale_contact_forms_return_404(self):
        kid = self.create()
        self.client.post(f"/kontakt/{kid}/loeschen")
        cases = [(f"/kontakt/{kid}/kanal", {"typ": "mobil", "wert": "000-test"}),
                 (f"/kontakt/{kid}/adresse", {"typ": "privat", "strasse": "Testweg", "plz": "97070", "ort": "Würzburg"}),
                 (f"/kontakt/{kid}", {"vorname": "Anna", "nachname": "Muster"})]
        for route, data in cases:
            with self.subTest(route=route):
                self.assertEqual(self.client.post(route, data=data).status_code, 404)

    def test_invalid_group_rolls_back_contact_edit(self):
        kid = self.create()
        gid = self.group()
        self.query("INSERT INTO kontakt_gruppe VALUES (?, ?)", (kid, gid))
        response = self.client.post(f"/kontakt/{kid}", data={"vorname": "Geändert", "nachname": "Muster", "gruppen": "999"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.query("SELECT vorname FROM kontakt")[0][0], "Anna")
        self.assertEqual(self.query("SELECT gruppe_id FROM kontakt_gruppe")[0][0], gid)

    def test_invalid_channel_type_returns_400(self):
        kid = self.create()
        response = self.client.post(f"/kontakt/{kid}/kanal", data={"typ": "unbekannt", "wert": "test"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.query("SELECT COUNT(*) FROM kanal")[0][0], 0)


if __name__ == "__main__":
    unittest.main()
