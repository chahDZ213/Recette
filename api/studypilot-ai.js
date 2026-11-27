// api/studypilot-ai.js — Professeur IA de StudyPilot (fonction serverless Vercel).
// Un seul point d'entrée, plusieurs "modes". La clé Anthropic reste côté serveur ;
// l'appel exige un compte Supabase et est plafonné par heure. Renvoie l'usage
// (tokens + coût estimé) pour le suivi de consommation dans l'app.
import Anthropic from "@anthropic-ai/sdk";

export const maxDuration = 120;
const MODEL = (process.env.STUDYPILOT_MODEL || "").trim() || "claude-opus-5-5";
const PRIX = { "claude-opus-5-5": [4, 20], "claude-sonnet-5-5": [2, 10], "claude-haiku-5-5": [0.1, 0.5] }; // $/MTok
const SB_URL = process.env.SUPABASE_URL || "https://hpejfttwocclmqdtdiok.supabase.co";
const SB_ANON = process.env.SUPABASE_ANON_KEY || "sb_publishable_vXQvAJWpR0kKwQ-Fo9aWLw__0x3B7k5";
const MAX_PAR_HEURE = Number(process.env.STUDYPILOT_MAX_PER_HOUR || 60);
const client = new Anthropic();

const hits = new Map();
function rateLimited(id) {
  const now = Date.now(), l = (hits.get(id) || []).filter((t) => now - t < 3600_000);
  if (l.length >= MAX_PAR_HEURE) return true;
  l.push(now); hits.set(id, l); return false;
}
async function userId(req) {
  const jwt = (req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (!jwt) return null;
  try {
    const r = await fetch(SB_URL + "/auth/v1/user", { headers: { apikey: SB_ANON, authorization: "Bearer " + jwt } });
    return r.ok ? (await r.json()).id : null;
  } catch { return null; }
}

const PROFIL = `Élève de première générale (2026-2027), spécialités maths, physique-chimie, sciences de l'ingénieur.
Objectif : BUT GEII en 2028. Passionné d'électronique, mécanique auto, programmation, ESP32, impression 3D.
Niveau actuel : maths ~10, PC ~8, anglais 16-17, français ~10. Compétent mais travaille peu : sois motivant, concret, bref.`;

const SYS = {
  tuteur: `Tu es le professeur particulier de cet élève. ${PROFIL}
Règles : ne donne JAMAIS directement la réponse d'un exercice ; fais raisonner (questions, indices gradués, vérification).
Repère et nomme l'erreur (formule, calcul, unité, connaissance, compréhension, raisonnement). Si l'élève ne comprend pas,
réexplique AUTREMENT (autre analogie, schéma en texte, exemple auto/ESP32/moteur électrique quand c'est pertinent).
Respecte le programme officiel de première. Formules en notation lisible (x², √, ·). Réponses courtes, en français.`,
  lecon: `Tu prépares une découverte anticipée d'une notion pour cet élève. ${PROFIL}
Produis : utilité concrète, cours simple, exemple détaillé, 4 exercices progressifs (découverte → niveau contrôle)
avec solutions détaillées vérifiées, et 2 questions de vérification de compréhension. Reste dans le programme de première.`,
  exercices: `Tu génères des exercices pour cet élève. ${PROFIL}
Énoncés autonomes, données numériques cohérentes, corrections détaillées que tu as vérifiées pas à pas (recalcule).
Contextes liés à ses passions quand c'est naturel. Respecte strictement le niveau demandé et le programme de première.`,
  correction: `Tu corriges la réponse d'un élève. ${PROFIL}
Compare à la solution attendue, donne un score de 0 à 1, classe chaque erreur, et un retour bref qui fait progresser
(indice plutôt que solution si le score < 1). Sois juste : une réponse équivalente correcte vaut 1.`,
  document: `Tu analyses un document scolaire (photo de cours manuscrit, PDF, contrôle corrigé, bulletin, emploi du temps,
devoirs, capture Pronote) d'un élève de première générale. Identifie le type, la matière, les notions (parmi la liste fournie
si possible), et extrais les données structurées (notes, devoirs, créneaux). Ne devine pas : si un élément est illisible ou
incertain, mets-le dans "incertitudes" avec une question à poser à l'élève et confiance < 0.7.`,
};

const S = (props, req = Object.keys(props)) => ({ type: "object", properties: props, required: req, additionalProperties: false });
const str = { type: "string" }, num = { type: "number" };
const arr = (items) => ({ type: "array", items });
const EXO = S({ enonce: str, niveau: str, indices: arr(str), solution: str, reponse_attendue: str });
const SCHEMAS = {
  lecon: S({ utilite: str, cours: str, exemple: str, exercices: arr(EXO), verification: arr(S({ question: str, reponse_attendue: str })) }),
  exercices: S({ exercices: arr(EXO) }),
  correction: S({ score: num, erreurs: arr({ type: "string", enum: ["formule", "calcul", "unite", "connaissance", "comprehension", "raisonnement"] }), retour: str }),
  document: S({
    type: { type: "string", enum: ["cours", "exercice", "controle", "bulletin", "emploi_du_temps", "devoirs", "pronote", "autre"] },
    matiere: str, titre: str, resume: str, confiance: num, notions: arr(str),
    notes: arr(S({ matiere: str, valeur: num, bareme: num, coef: num, date: str, intitule: str })),
    devoirs: arr(S({ matiere: str, titre: str, date: str, type: { type: "string", enum: ["devoir", "controle"] } })),
    creneaux: arr(S({ jour: num, debut: str, fin: str, matiere: str })),
    appreciations: arr(S({ matiere: str, texte: str })),
    incertitudes: arr(S({ element: str, question: str })),
  }),
};

function cout(model, u) {
  const [pi, po] = PRIX[model] || PRIX["claude-opus-5-5"];
  const inTok = (u.input_tokens || 0) + (u.cache_creation_input_tokens || 0) * 1.25 + (u.cache_read_input_tokens || 0) * 0.1;
  return (inTok * pi + (u.output_tokens || 0) * po) / 1e6;
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST uniquement" });
  if (!process.env.ANTHROPIC_API_KEY) return res.status(503).json({ error: "IA non configurée (ANTHROPIC_API_KEY)" });
  const uid = await userId(req);
  if (!uid) return res.status(401).json({ error: "Connexion requise" });
  if (rateLimited(uid)) return res.status(429).json({ error: "Trop de requêtes, réessaie dans un moment" });

  const { mode, messages = [], prompt = "", fichier, contexte = "" } = req.body || {};
  if (!SYS[mode]) return res.status(400).json({ error: "mode inconnu" });

  let msgs;
  if (mode === "tuteur") {
    msgs = messages.slice(-30).filter((m) => ["user", "assistant"].includes(m.role) && typeof m.content === "string")
      .map((m) => ({ role: m.role, content: m.content.slice(0, 8000) }));
    if (!msgs.length || msgs[0].role !== "user") return res.status(400).json({ error: "conversation vide" });
  } else {
    const content = [];
    if (fichier?.data) {
      const media = String(fichier.type || "");
      if (media === "application/pdf") content.push({ type: "document", source: { type: "base64", media_type: media, data: fichier.data } });
      else if (/^image\/(png|jpeg|gif|webp)$/.test(media)) content.push({ type: "image", source: { type: "base64", media_type: media, data: fichier.data } });
      else return res.status(400).json({ error: "format non pris en charge (image ou PDF)" });
    }
    content.push({ type: "text", text: `${contexte ? "Contexte :\n" + String(contexte).slice(0, 12000) + "\n\n" : ""}${String(prompt).slice(0, 8000)}` });
    msgs = [{ role: "user", content }];
  }

  try {
    const params = {
      model: MODEL, max_tokens: mode === "tuteur" ? 4000 : 16000,
      betas: ["server-side-fallback-2026-07-01"], fallbacks: "default",
      system: [{ type: "text", text: SYS[mode], cache_control: { type: "ephemeral" } }],
      output_config: { effort: mode === "tuteur" ? "low" : "medium", ...(SCHEMAS[mode] ? { format: { type: "json_schema", schema: SCHEMAS[mode] } } : {}) },
      messages: msgs,
    };
    const r = await client.beta.messages.stream(params).finalMessage();
    if (r.stop_reason === "refusal") return res.status(422).json({ error: "Demande refusée par le modèle" });
    const text = r.content.filter((b) => b.type === "text").map((b) => b.text).join("");
    let data = text;
    if (SCHEMAS[mode]) { try { data = JSON.parse(text); } catch { return res.status(502).json({ error: "Réponse IA illisible, réessaie" }); } }
    const usage = { model: r.model, input: r.usage.input_tokens, output: r.usage.output_tokens, cout: cout(r.model, r.usage) };
    return res.status(200).json({ data, usage });
  } catch (e) {
    if (e instanceof Anthropic.RateLimitError) return res.status(429).json({ error: "IA saturée, réessaie dans une minute" });
    if (e instanceof Anthropic.APIError) return res.status(502).json({ error: `Erreur IA (${e.status})` });
    return res.status(500).json({ error: "Erreur serveur" });
  }
}
