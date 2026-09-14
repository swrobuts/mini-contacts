// Zusätzliche Tests für die Formularereignisse: node --test tests/test_ui.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../static/app.js"), "utf8");

function target(properties = {}) {
  const listeners = new Map();
  return Object.assign(properties, {
    addEventListener(type, listener) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(listener);
    },
    emit(type, event) {
      for (const listener of listeners.get(type) || []) listener(event);
    },
  });
}

function setup(confirmText = "Anna Muster wirklich löschen?") {
  const details = target({method: "post", entries: [["vorname", "Anna"]], dataset: {}});
  const channel = target({method: "post", entries: [["wert", ""]], dataset: {}});
  const deletion = target({method: "post", entries: [], dataset: {confirm: confirmText}});
  const forms = [details, channel, deletion];
  const prompts = [];
  let answer = false;
  const window = target({confirm(message) { prompts.push(message); return answer; }});
  const document = target({forms, querySelectorAll() { return [deletion]; }});
  const context = vm.createContext({document, window, FormData: class {
    constructor(form) { this.entries = form.entries; }
    [Symbol.iterator]() { return this.entries[Symbol.iterator](); }
  }});
  vm.runInContext(source, context);
  function event(form) {
    return {target: form, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }};
  }
  return {details, channel, deletion, prompts, context,
    answer(value) { answer = value; },
    submit(form) {
      const e = event(form);
      form.emit("submit", e);
      document.emit("submit", e);
      return e;
    },
    unload() { const e = event(); window.emit("beforeunload", e); return e; },
    restore() { window.emit("pageshow", event()); },
  };
}

test("Sonderzeichen und Codefragmente bleiben unveränderter Bestätigungstext", () => {
  for (const name of ["O'Connor", 'Muster "Test"', "Back\\slash", "Zeile\numbruch",
                     "'+(globalThis.marker=123)+'", "&quot;&#39;", '"><script>marker=123</script>']) {
    const text = `${name} Muster wirklich löschen?`;
    const ui = setup(text);
    assert.equal(ui.submit(ui.deletion).defaultPrevented, true);
    assert.deepEqual(ui.prompts, [text]);
    assert.equal(ui.context.marker, undefined);
    ui.answer(true);
    assert.equal(ui.submit(ui.deletion).defaultPrevented, false);
  }
});

test("Abbrechen schützt die Eingaben anderer Bereiche", () => {
  const ui = setup();
  ui.details.entries = [["vorname", "Annika"], ["notiz", "Entwurf"], ["gruppen", "1"]];
  ui.channel.entries = [["wert", "000-test"]];
  assert.equal(ui.submit(ui.channel).defaultPrevented, true);
  assert.equal(ui.prompts.length, 1);
  assert.match(ui.prompts[0], /ungespeicherte Änderungen/);
  assert.equal(ui.details.entries[0][1], "Annika");
  assert.equal(ui.unload().defaultPrevented, true);
});

test("Bewusstes Verwerfen erlaubt die Aktion ohne doppelte Warnung", () => {
  const ui = setup();
  ui.details.entries = [["vorname", "Annika"]];
  ui.answer(true);
  assert.equal(ui.submit(ui.channel).defaultPrevented, false);
  assert.equal(ui.unload().defaultPrevented, false);
  ui.restore();
  assert.equal(ui.unload().defaultPrevented, true);
});

test("Speichern des einzigen geänderten Formulars benötigt keine Warnung", () => {
  const ui = setup();
  ui.details.entries = [["vorname", "Annika"]];
  assert.equal(ui.submit(ui.details).defaultPrevented, false);
  assert.deepEqual(ui.prompts, []);
  assert.equal(ui.unload().defaultPrevented, false);
});

test("Zurückgesetzte Eingaben gelten nicht mehr als ungespeichert", () => {
  const ui = setup();
  ui.details.entries = [["vorname", "Annika"]];
  assert.equal(ui.unload().defaultPrevented, true);
  ui.details.entries = [["vorname", "Anna"]];
  assert.equal(ui.unload().defaultPrevented, false);
});

test("Nach einem Validierungsfehler wieder angezeigte Entwürfe bleiben geschützt", () => {
  const ui = setup();
  ui.details.dataset.unsaved = "true";
  assert.equal(ui.submit(ui.channel).defaultPrevented, true);
  assert.equal(ui.unload().defaultPrevented, true);
  ui.prompts.length = 0;
  assert.equal(ui.submit(ui.details).defaultPrevented, false);
  assert.deepEqual(ui.prompts, []);
});

test("Abgebrochene Löschbestätigung löst keine weitere Warnung aus", () => {
  const ui = setup();
  ui.details.entries = [["vorname", "Annika"]];
  assert.equal(ui.submit(ui.deletion).defaultPrevented, true);
  assert.deepEqual(ui.prompts, ["Anna Muster wirklich löschen?"]);
  assert.equal(ui.unload().defaultPrevented, true);
});
