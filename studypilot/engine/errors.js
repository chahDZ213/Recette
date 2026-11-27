export const TYPES_ERREUR = {
  formule: "Formule mal utilisée", calcul: "Erreur de calcul", unite: "Problème d'unité",
  connaissance: "Manque de connaissances", comprehension: "Mauvaise compréhension", raisonnement: "Erreur de raisonnement",
};
export const NIVEAUX = ["decouverte", "application", "controle", "approfondissement", "bac"];
export const NIVEAU_LABEL = { decouverte: "Découverte", application: "Application directe", controle: "Niveau contrôle", approfondissement: "Approfondissement", bac: "Niveau bac" };

// Bilan des erreurs : { notionId: { type: n } } → erreurs dominantes
export function bilanErreurs(tentatives) {
  const par = {};
  for (const t of tentatives) for (const e of t.erreurs || []) {
    ((par[t.notion] ||= {})[e] = (par[t.notion][e] || 0) + 1);
  }
  return par;
}
export function erreurDominante(bilan, notion) {
  const e = Object.entries(bilan[notion] || {}).sort((a, b) => b[1] - a[1]);
  return e[0]?.[0] || null;
}
// Niveau suivant selon la réussite récente sur la notion
export function niveauSuivant(tentatives, notion) {
  const l = tentatives.filter((t) => t.notion === notion).slice(-3);
  if (!l.length) return "decouverte";
  const dernier = NIVEAUX.indexOf(l.at(-1).niveau);
  const moy = l.reduce((s, t) => s + t.score, 0) / l.length;
  if (moy >= 0.8) return NIVEAUX[Math.min(dernier + 1, 4)];
  if (moy < 0.5) return NIVEAUX[Math.max(dernier - 1, 0)];
  return NIVEAUX[Math.max(dernier, 0)];
}
