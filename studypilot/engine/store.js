// Persistance : état JSON (localStorage, synchronisé Supabase) + fichiers (IndexedDB).
const KEY = "studypilot_state_v1";
export const ETAT_INITIAL = () => ({
  version: 1, maj: 0,
  profil: { objectif: "BUT GEII (2028)", cibles: { maths: 13, pc: 12, si: 14, fr: 12 } },
  progression: {},   // notionId → état SRS + statut
  ordreProf: {},     // matiere → [notionId] (ordre réellement suivi)
  notes: [],         // {id, matiere, valeur, bareme, coef, date, trimestre, intitule}
  devoirs: [],       // {id, matiere, titre, date, type: devoir|controle, fait, notions}
  edt: [],           // {jour 0-6, debut, fin, matiere}
  indispos: [],      // {date, motif}
  documents: [],     // métadonnées {id, nom, type, matiere, notions, resume, date, fichierId, aConfirmer}
  tentatives: [],    // {date, notion, niveau, score, erreurs}
  sessions: [],      // {date, minutes, blocs faits}
  appreciations: [], // {trimestre, matiere, texte}
  chat: [],          // conversation du professeur IA
  usageIA: [],
  supprimes: [],     // ids supprimés (pour la synchro)       // {date, mode, cout, input, output}
  bac: {},           // valeurs saisies pour la simulation
});

export function charger(storage = globalThis.localStorage) {
  try { const s = JSON.parse(storage.getItem(KEY)); if (s?.version) return { ...ETAT_INITIAL(), ...s }; } catch {}
  return ETAT_INITIAL();
}
export function sauver(state, storage = globalThis.localStorage) {
  state.maj = Date.now();
  storage.setItem(KEY, JSON.stringify(state));
  return state;
}
export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

// Fusion simple local/distant : le plus récent gagne, mais aucune liste n'est perdue
// (union par id des notes, devoirs, documents, tentatives).
export function fusionner(local, distant) {
  if (!distant?.version) return local;
  const [rec, anc] = (distant.maj || 0) > (local.maj || 0) ? [distant, local] : [local, distant];
  const out = { ...ETAT_INITIAL(), ...rec };
  out.supprimes = [...new Set([...(rec.supprimes || []), ...(anc.supprimes || [])])];
  const del = new Set(out.supprimes);
  for (const k of ["notes", "devoirs", "documents", "tentatives", "sessions", "usageIA"]) {
    const ids = new Set((rec[k] || []).map((x) => x.id ?? JSON.stringify(x)));
    out[k] = [...(rec[k] || []), ...(anc[k] || []).filter((x) => !ids.has(x.id ?? JSON.stringify(x)))].filter((x) => !del.has(x.id));
  }
  return out;
}

// --- Fichiers (IndexedDB) ---
function db() {
  return new Promise((ok, ko) => {
    const r = indexedDB.open("studypilot", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("fichiers");
    r.onsuccess = () => ok(r.result); r.onerror = () => ko(r.error);
  });
}
export async function fichierPut(id, blob) {
  const d = await db();
  return new Promise((ok, ko) => { const t = d.transaction("fichiers", "readwrite"); t.objectStore("fichiers").put(blob, id); t.oncomplete = ok; t.onerror = () => ko(t.error); });
}
export async function fichierGet(id) {
  const d = await db();
  return new Promise((ok, ko) => { const r = d.transaction("fichiers").objectStore("fichiers").get(id); r.onsuccess = () => ok(r.result); r.onerror = () => ko(r.error); });
}
export async function fichierDel(id) {
  const d = await db();
  return new Promise((ok) => { const t = d.transaction("fichiers", "readwrite"); t.objectStore("fichiers").delete(id); t.oncomplete = ok; });
}
