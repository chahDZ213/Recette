// Moteur de planification : construit une séance pour un temps donné.
// Fonction pure : (état, date, minutes) → séance. Recalculée à chaque changement.
import { toutesNotions, MATIERES } from "./curriculum.js";
import { estDue, risqueOubli, diffJours, parseIso, iso, addDays } from "./srs.js";
import { moyennesParMatiere } from "./grades.js";

const PRIO = Object.fromEntries(MATIERES.map((m) => [m.id, m.prio]));
const DUREE = { devoir: 20, controle: 25, revision: 10, anticipation: 15, consolidation: 15, cours_demain: 10 };

export function candidats(state, now = new Date()) {
  const notions = toutesNotions();
  const byId = Object.fromEntries(notions.map((n) => [n.id, n]));
  const prog = state.progression || {};
  const moy = moyennesParMatiere(state.notes || []);
  const faiblesse = (m) => (moy[m] == null ? 1 : Math.max(0.5, (14 - moy[m]) / 4)); // < 14 → bonus
  const today = iso(now), demain = iso(addDays(now, 1));
  const out = [];

  for (const d of state.devoirs || []) {
    if (d.fait || d.date < today) continue;
    const j = diffJours(now, parseIso(d.date));
    if (d.type === "controle") {
      if (j > 10) continue;
      out.push({ type: "controle", ref: d.id, matiere: d.matiere, notions: d.notions || [], titre: `Préparer : ${d.titre}`,
        score: 100 / (j + 1) * PRIO[d.matiere] || 30, minutes: DUREE.controle, raison: j <= 1 ? "Contrôle demain !" : `Contrôle dans ${j} j` });
    } else {
      if (j > 7) continue;
      out.push({ type: "devoir", ref: d.id, matiere: d.matiere, titre: d.titre, minutes: d.minutes || DUREE.devoir,
        score: 90 / (j + 0.5), raison: j <= 1 ? "À rendre demain" : `À rendre dans ${j} j` });
    }
  }
  // Cours de demain (emploi du temps) → relire le dernier chapitre en cours
  const jsem = addDays(now, 1).getDay();
  const matDemain = new Set((state.edt || []).filter((c) => c.jour === jsem).map((c) => c.matiere));
  for (const ind of state.indispos || []) if (ind.date === demain) matDemain.clear();
  for (const m of matDemain) {
    const enCours = notions.find((n) => n.matiere === m && prog[n.id]?.statut === "en_cours");
    if (enCours) out.push({ type: "cours_demain", notion: enCours.id, matiere: m, titre: `Relire : ${enCours.titre}`,
      score: 25 * PRIO[m], minutes: DUREE.cours_demain, raison: "Cours demain" });
  }
  // Révisions espacées dues + notions à consolider
  for (const n of notions) {
    const e = prog[n.id];
    if (!e) continue;
    if (e.statut === "a_consolider") out.push({ type: "consolidation", notion: n.id, matiere: n.matiere, titre: `Consolider : ${n.titre}`,
      score: 30 * PRIO[n.matiere] * faiblesse(n.matiere), minutes: DUREE.consolidation, raison: "Erreurs récentes" });
    else if (estDue(e, now)) out.push({ type: "revision", notion: n.id, matiere: n.matiere, titre: `Réviser : ${n.titre}`,
      score: 15 * PRIO[n.matiere] * risqueOubli(e, now) * faiblesse(n.matiere), minutes: DUREE.revision, raison: "Risque d'oubli" });
  }
  // Anticipation : prochaine notion non étudiée dans l'ordre du prof, prérequis OK
  for (const m of ["maths", "pc", "si"]) {
    const ordre = (state.ordreProf?.[m] || []).map((id) => byId[id]).filter(Boolean);
    const liste = ordre.length ? ordre : notions.filter((n) => n.matiere === m);
    const next = liste.find((n) => !prog[n.id] || prog[n.id].statut === "non_etudiee");
    if (!next) continue;
    const preOk = next.prerequis.every((p) => ["etudiee", "maitrisee", "decouverte", "en_cours"].includes(prog[p]?.statut));
    out.push({ type: "anticipation", notion: next.id, matiere: m, titre: `Découvrir en avance : ${next.titre}`,
      score: 12 * PRIO[m], minutes: DUREE.anticipation, raison: preOk ? "Prochain chapitre" : "Prérequis à vérifier d'abord", prerequisManquants: preOk ? [] : next.prerequis });
  }
  return out.sort((a, b) => b.score - a.score);
}

export function planifier(state, minutes, now = new Date()) {
  const c = candidats(state, now);
  const blocs = [];
  let reste = minutes;
  const matieresVues = {};
  for (const x of c) {
    if (reste < 5) break;
    // diversité : pénalise une 3e tâche de la même matière (sauf contrôle/devoir)
    if ((matieresVues[x.matiere] || 0) >= 2 && !["controle", "devoir"].includes(x.type)) continue;
    const m = Math.min(x.minutes, reste);
    if (m < Math.min(x.minutes, 8)) continue;
    blocs.push({ ...x, minutes: m });
    reste -= m;
    matieresVues[x.matiere] = (matieresVues[x.matiere] || 0) + 1;
  }
  if (reste >= 5 && blocs.length) blocs[0].minutes += reste; // temps restant sur la priorité n°1
  return { date: iso(now), minutes, blocs, total: blocs.reduce((s, b) => s + b.minutes, 0) };
}
