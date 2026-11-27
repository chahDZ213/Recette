// Calcul des moyennes (méthode Pronote : moyenne pondérée par coefficients,
// notes ramenées sur 20) et simulation du bac.
export function sur20(n) { return n.bareme && n.bareme !== 20 ? (n.valeur / n.bareme) * 20 : n.valeur; }

export function moyenne(notes) {
  const v = notes.filter((n) => typeof n.valeur === "number" && !n.absent && !n.nonNote);
  const sc = v.reduce((s, n) => s + (n.coef ?? 1), 0);
  if (!sc) return null;
  return v.reduce((s, n) => s + sur20(n) * (n.coef ?? 1), 0) / sc;
}

export function moyennesParMatiere(notes, trimestre = null) {
  const out = {};
  for (const n of notes) if (trimestre == null || n.trimestre === trimestre) (out[n.matiere] ||= []).push(n);
  return Object.fromEntries(Object.entries(out).map(([m, l]) => [m, moyenne(l)]));
}

// Moyenne générale = moyenne (pondérée par coefMatiere, 1 par défaut) des moyennes de matières
export function moyenneGenerale(parMatiere, coefMatiere = {}) {
  const e = Object.entries(parMatiere).filter(([, v]) => v != null);
  const sc = e.reduce((s, [m]) => s + (coefMatiere[m] ?? 1), 0);
  return sc ? e.reduce((s, [m, v]) => s + v * (coefMatiere[m] ?? 1), 0) / sc : null;
}

// Quelle note faut-il au prochain devoir (coef c) pour atteindre la cible ?
export function noteNecessaire(notes, cible, coef = 1) {
  const v = notes.filter((n) => typeof n.valeur === "number");
  const sc = v.reduce((s, n) => s + (n.coef ?? 1), 0);
  const sp = v.reduce((s, n) => s + sur20(n) * (n.coef ?? 1), 0);
  return (cible * (sc + coef) - sp) / coef;
}

// Bac général (coefficients officiels sur 100) — fin de première : contrôle continu 1re,
// spécialité abandonnée (coef 8), épreuves anticipées de français (5+5) et l'épreuve anticipée
// de mathématiques (coef 2, en juin de première ; à vérifier sur Éduscol).
// Le terminal : 2 spécialités (16 chacune), philosophie (8), grand oral (10).
// Les coefficients de contrôle continu sont répartis 1re/Tle (HG 3+3, LV 3+3 ×2, ES 3+3, EPS 6, EMC 1+1).
export const COEFS_BAC = [
  { id: "fr_ecrit", nom: "Français écrit (EAF)", coef: 5, annee: 1 },
  { id: "fr_oral", nom: "Français oral (EAF)", coef: 5, annee: 1 },
  { id: "maths_anticipe", nom: "Épreuve anticipée de maths", coef: 2, annee: 1 },
  { id: "spe_abandon", nom: "Spécialité abandonnée (moy. 1re)", coef: 8, annee: 1 },
  { id: "spe1", nom: "Spécialité 1 (épreuve Tle)", coef: 16, annee: 2 },
  { id: "spe2", nom: "Spécialité 2 (épreuve Tle)", coef: 16, annee: 2 },
  { id: "philo", nom: "Philosophie", coef: 8, annee: 2 },
  { id: "grand_oral", nom: "Grand oral", coef: 10, annee: 2 },
  { id: "hg", nom: "Histoire-géo (CC)", coef: 6, annee: 0 },
  { id: "lva", nom: "LVA (CC)", coef: 6, annee: 0 },
  { id: "lvb", nom: "LVB (CC)", coef: 6, annee: 0 },
  { id: "es", nom: "Ens. scientifique (CC)", coef: 6, annee: 0 },
  { id: "eps", nom: "EPS (CC)", coef: 6, annee: 0 },
  { id: "emc", nom: "EMC (CC)", coef: 2, annee: 0 },
];
export const TOTAL_COEFS = COEFS_BAC.reduce((s, x) => s + x.coef, 0); // 100 + 2 (maths anticipées)
// Valeurs manquantes = ignorées (simulation partielle).
export function simulerBac(valeurs) {
  let s = 0, c = 0;
  for (const x of COEFS_BAC) { const v = valeurs[x.id]; if (typeof v === "number") { s += v * x.coef; c += x.coef; } }
  return c ? { moyenne: s / c, couverture: c / TOTAL_COEFS } : null;
}
export function mention(m) { return m >= 16 ? "Très bien" : m >= 14 ? "Bien" : m >= 12 ? "Assez bien" : m >= 10 ? "Admis" : "Non admis (oral de rattrapage si ≥ 8)"; }
