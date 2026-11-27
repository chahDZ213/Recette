import test from "node:test";
import assert from "node:assert/strict";
import { moyenne, moyennesParMatiere, moyenneGenerale, noteNecessaire, simulerBac, TOTAL_COEFS } from "../engine/grades.js";
import { enregistrer, nouvelEtat, estDue, iso, addDays } from "../engine/srs.js";
import { planifier } from "../engine/planner.js";
import { toutesNotions } from "../engine/curriculum.js";
import { niveauSuivant } from "../engine/errors.js";

const D = new Date(2026, 10, 27);

test("moyenne pondérée et barèmes", () => {
  assert.equal(moyenne([{ valeur: 10, coef: 1 }, { valeur: 16, coef: 2 }]), 14);
  assert.equal(moyenne([{ valeur: 5, bareme: 10, coef: 1 }]), 10);
  assert.equal(moyenne([{ valeur: 12, absent: true }]), null);
  const pm = moyennesParMatiere([{ matiere: "maths", valeur: 8 }, { matiere: "maths", valeur: 12 }, { matiere: "ang", valeur: 17 }]);
  assert.deepEqual(pm, { maths: 10, ang: 17 });
  assert.equal(moyenneGenerale(pm), 13.5);
});
test("note nécessaire", () => {
  assert.equal(noteNecessaire([{ valeur: 10 }, { valeur: 10 }], 12, 2), 14);
});
test("simulation bac", () => {
  assert.equal(TOTAL_COEFS, 102);
  const r = simulerBac({ fr_ecrit: 10, fr_oral: 14 });
  assert.equal(r.moyenne, 12);
});
test("répétition espacée : progression et échec", () => {
  let e = enregistrer(nouvelEtat(), 1, D);
  assert.equal(e.prochaine, iso(addDays(D, 1)));
  e = enregistrer(e, 1, addDays(D, 1));
  assert.equal(e.prochaine, iso(addDays(D, 4)));
  assert.notEqual(e.statut, "maitrisee");
  e = enregistrer(e, 0.2, addDays(D, 4));
  assert.equal(e.statut, "a_consolider");
  assert.equal(e.prochaine, iso(addDays(D, 5)));
  assert.ok(estDue(e, addDays(D, 5)) && !estDue(e, addDays(D, 4)));
});
test("maîtrise uniquement après plusieurs réussites espacées", () => {
  let e = nouvelEtat(), d = D;
  for (let i = 0; i < 3; i++) { e = enregistrer(e, 1, d); d = addDays(d, 7); }
  assert.notEqual(e.statut, "maitrisee");
  e = enregistrer(e, 1, d);
  assert.equal(e.statut, "maitrisee");
});
test("planning : contrôle prioritaire, respecte le temps", () => {
  const state = {
    devoirs: [
      { id: "c1", type: "controle", matiere: "pc", titre: "DS énergie", date: iso(addDays(D, 1)) },
      { id: "d1", type: "devoir", matiere: "hg", titre: "Fiche", date: iso(addDays(D, 6)) },
    ],
    progression: { "m-suites-def": { ...enregistrer(nouvelEtat(), 1, addDays(D, -3)) } },
    notes: [{ matiere: "pc", valeur: 8 }],
  };
  for (const min of [15, 30, 45, 60, 90]) {
    const p = planifier(state, min, D);
    assert.equal(p.blocs[0].type, "controle");
    assert.ok(p.total <= min, `total ${p.total} > ${min}`);
  }
  const p = planifier(state, 90, D);
  assert.ok(p.blocs.some((b) => b.type === "revision"));
  assert.ok(p.blocs.some((b) => b.type === "anticipation"));
});
test("planning recalculé après devoir rendu", () => {
  const state = { devoirs: [{ id: "c1", type: "controle", matiere: "pc", titre: "DS", date: iso(addDays(D, 1)), fait: true }] };
  assert.ok(!planifier(state, 30, D).blocs.some((b) => b.type === "controle"));
});
test("programme : ids uniques, prérequis existants", () => {
  const n = toutesNotions(); const ids = new Set(n.map((x) => x.id));
  assert.equal(ids.size, n.length);
  for (const x of n) for (const p of x.prerequis) assert.ok(ids.has(p), `${x.id} → ${p}`);
});
test("niveau d'exercice adaptatif", () => {
  assert.equal(niveauSuivant([], "a"), "decouverte");
  assert.equal(niveauSuivant([{ notion: "a", niveau: "application", score: 1 }], "a"), "controle");
  assert.equal(niveauSuivant([{ notion: "a", niveau: "controle", score: 0.2 }], "a"), "application");
});
import { fusionner, ETAT_INITIAL, charger, sauver } from "../engine/store.js";
test("sauvegarde et fusion multi-appareil", () => {
  const mem = { d: {}, getItem(k) { return this.d[k] ?? null; }, setItem(k, v) { this.d[k] = v; } };
  const s = ETAT_INITIAL(); s.notes.push({ id: "a", matiere: "maths", valeur: 12 });
  sauver(s, mem);
  assert.equal(charger(mem).notes[0].valeur, 12);
  const distant = { ...ETAT_INITIAL(), maj: s.maj + 10, notes: [{ id: "b", matiere: "pc", valeur: 9 }], supprimes: [] };
  const f = fusionner(s, distant);
  assert.deepEqual(f.notes.map((n) => n.id).sort(), ["a", "b"]);
  const f2 = fusionner(s, { ...distant, supprimes: ["a"] });
  assert.deepEqual(f2.notes.map((n) => n.id), ["b"]);
});
