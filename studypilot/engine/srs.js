// Répétition espacée : intervalles J+1, 3, 7, 14, 30, 60. Un échec fait reculer.
// "Maîtrisée" exige ≥ 3 réussites espacées consécutives dont une à J+14 ou plus.
export const INTERVALLES = [1, 3, 7, 14, 30, 60];
const DAY = 86400000;
export const jour = (d = new Date()) => { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; };
export const addDays = (d, n) => new Date(jour(d).getTime() + n * DAY);
export const iso = (d) => { const x = jour(d); return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`; };
export const parseIso = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
export const diffJours = (a, b) => Math.round((jour(b) - jour(a)) / DAY);

export function nouvelEtat() { return { palier: -1, serie: 0, prochaine: null, historique: [], statut: "non_etudiee" }; }

// score ∈ [0,1] (fraction de réussite de la session sur cette notion)
export function enregistrer(etat, score, date = new Date(), source = "lycee") {
  const e = structuredClone(etat || nouvelEtat());
  e.historique.push({ date: iso(date), score });
  if (score >= 0.8) { e.palier = Math.min(e.palier + 1, INTERVALLES.length - 1); e.serie++; }
  else if (score >= 0.5) { e.palier = Math.max(e.palier, 0); e.serie = 0; }
  else { e.palier = Math.max(-1, e.palier - 2); e.serie = 0; }
  const interv = e.palier < 0 ? 1 : INTERVALLES[e.palier];
  e.prochaine = iso(addDays(date, interv));
  e.statut = statutDepuis(e, source);
  return e;
}

export function statutDepuis(e, source) {
  if (!e.historique.length) return e.statut || "non_etudiee";
  const dernier = e.historique.at(-1).score;
  if (e.serie >= 3 && e.palier >= 3) return "maitrisee";
  if (dernier < 0.6) return "a_consolider";
  if (source === "anticipation" && e.statut !== "en_cours" && e.statut !== "etudiee") return "decouverte";
  return e.statut === "en_cours" ? "en_cours" : "etudiee";
}

export function estDue(e, aujourdhui = new Date()) {
  return !!e?.prochaine && diffJours(parseIso(e.prochaine), aujourdhui) >= 0;
}
// Risque d'oubli ~ retard relatif à l'intervalle courant
export function risqueOubli(e, aujourdhui = new Date()) {
  if (!e?.prochaine) return 0;
  const interv = e.palier < 0 ? 1 : INTERVALLES[e.palier];
  const retard = diffJours(parseIso(e.prochaine), aujourdhui);
  return Math.max(0, Math.min(2, 1 + retard / interv));
}
