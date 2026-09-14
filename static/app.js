"use strict";

// Namen sind Daten, kein Bestandteil von ausführbarem JavaScript.
for (const form of document.querySelectorAll("form[data-confirm]")) {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
}

// Jeder Bereich hat sein eigenes Formular. Ein Seitenwechsel darf die
// noch nicht gespeicherten Eingaben der anderen Bereiche nicht still verwerfen.
const forms = Array.from(document.forms).filter((form) => form.method === "post");
const snapshot = (form) => JSON.stringify(Array.from(new FormData(form)));
const initial = new Map(forms.map((form) => [form, snapshot(form)]));
const isDirty = (form) => form.dataset.unsaved === "true" || snapshot(form) !== initial.get(form);
let leaving = false;

document.addEventListener("submit", (event) => {
  if (event.defaultPrevented) return;
  if (forms.some((form) => form !== event.target && isDirty(form))) {
    if (!window.confirm("In einem anderen Bereich gibt es ungespeicherte Änderungen. " +
                        "Diese verwerfen und fortfahren?")) {
      event.preventDefault();
      return;
    }
  }
  leaving = true;
});

window.addEventListener("beforeunload", (event) => {
  if (!leaving && forms.some(isDirty)) {
    event.preventDefault();
    event.returnValue = "";
  }
});

// Beim Zurücknavigieren kann der Browser die gesamte Seite wiederherstellen.
window.addEventListener("pageshow", () => { leaving = false; });
