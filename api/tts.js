// api/tts.js — Fonction serverless Vercel (Node)
// Lecture vocale premium du mode cuisson via ElevenLabs.
// Reçoit { text, lang }, renvoie l'audio MP3. Sans clé configurée -> 501,
// et l'appli retombe silencieusement sur la voix du navigateur.
//
// Variables d'environnement Vercel :
//   ELEVENLABS_API_KEY   (obligatoire pour activer la voix premium)
//   ELEVENLABS_VOICE_ID  (optionnel — défaut : Rachel "21m00Tcm4TlvDq8ikWAM";
//                         mets l'ID d'une voix de ta bibliothèque ElevenLabs)
//   ELEVENLABS_MODEL     (optionnel — défaut "eleven_multilingual_v2",
//                         "eleven_flash_v2_5" = moins cher et plus rapide)

export const maxDuration = 30;

const KEY = process.env.ELEVENLABS_API_KEY;
const VOICE = (process.env.ELEVENLABS_VOICE_ID || "").trim() || "21m00Tcm4TlvDq8ikWAM";
const MODEL = (process.env.ELEVENLABS_MODEL || "").trim() || "eleven_multilingual_v2";

// ElevenLabs facture au caractère : compte obligatoire et plafond horaire.
const SB_URL = process.env.SUPABASE_URL || "https://hpejfttwocclmqdtdiok.supabase.co";
const SB_ANON = process.env.SUPABASE_ANON_KEY || "sb_publishable_vXQvAJWpR0kKwQ-Fo9aWLw__0x3B7k5";
const MAX_PER_HOUR = 300;   // large : une recette longue = quelques dizaines d'étapes lues
const hits = new Map();
function rateLimited(userId) {
  const now = Date.now();
  const list = (hits.get(userId) || []).filter((t) => now - t < 3600_000);
  if (list.length >= MAX_PER_HOUR) { hits.set(userId, list); return true; }
  list.push(now); hits.set(userId, list);
  if (hits.size > 5000) { for (const k of hits.keys()) { hits.delete(k); if (hits.size <= 2500) break; } }
  return false;
}
async function supabaseUserId(req) {
  const jwt = (req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (!jwt) return null;
  try {
    const u = await fetch(SB_URL + "/auth/v1/user", { headers: { apikey: SB_ANON, authorization: "Bearer " + jwt } });
    if (!u.ok) return null;
    return (await u.json()).id || null;
  } catch { return null; }
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });
  // même protection d'origine que /api/extract
  const allowed = (process.env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (allowed.length) {
    const src = req.headers.origin || req.headers.referer || "";
    if (src && !allowed.some((a) => src.startsWith(a))) {
      return res.status(403).json({ error: "Origine non autorisée" });
    }
  }
  if (!KEY) return res.status(501).json({ error: "Voix premium non configurée" });
  const userId = await supabaseUserId(req);
  if (!userId) return res.status(401).json({ error: "Connexion requise" });
  if (rateLimited(userId)) return res.status(429).json({ error: "Trop de lectures d'affilée. Réessaie plus tard." });
  try {
    const body = req.body || {};
    const text = (typeof body.text === "string" ? body.text : "").trim().slice(0, 900);
    if (text.length < 2) return res.status(400).json({ error: "Texte manquant" });
    const lang = body.lang === "en" ? "en" : "fr";
    const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE}?output_format=mp3_44100_64`, {
      method: "POST",
      headers: { "xi-api-key": KEY, "content-type": "application/json" },
      body: JSON.stringify({
        text,
        model_id: MODEL,
        // le modèle multilingue détecte la langue ; language_code aide les modèles flash/turbo
        ...(MODEL.includes("flash") || MODEL.includes("turbo") ? { language_code: lang } : {}),
      }),
    });
    if (!r.ok) {
      const err = await r.text().catch(() => "");
      console.error("tts: erreur ElevenLabs", r.status, err.slice(0, 300));
      return res.status(502).json({ error: "Synthèse vocale indisponible" });
    }
    const audio = Buffer.from(await r.arrayBuffer());
    res.setHeader("content-type", "audio/mpeg");
    res.setHeader("cache-control", "no-store");
    return res.status(200).send(audio);
  } catch (e) {
    console.error("tts: échec", e && e.message);
    return res.status(502).json({ error: "Synthèse vocale indisponible" });
  }
}
