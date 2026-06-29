// api/extract.js — Fonction serverless Vercel (Node)
// Reçoit { url } ou { text }, renvoie une recette structurée en JSON.
// Transcript via Supadata (fiable depuis Vercel + fallback Whisper sur vidéos sans sous-titres).

export const maxDuration = 60;

const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;
const SUPADATA_KEY = process.env.SUPADATA_API_KEY;
const YT_KEY = process.env.YOUTUBE_API_KEY; // optionnel

const INSTRUCTIONS = `Tu renvoies UNIQUEMENT un objet JSON, sans aucun texte autour, sans backticks. Format exact :
{
  "found": true,
  "title": "Nom du plat",
  "baseServings": 4,
  "ingredients": [{"name": "farine", "amount": 250, "unit": "g"}],
  "steps": [{"title": "Titre court", "content": "Instruction claire", "timerSeconds": 600}]
}
Règles :
- "amount" est un nombre (ou null si non quantifiable). "unit" peut être null (ex: oeufs, gousses).
- "baseServings" = nombre de personnes de la recette d'origine. Si non précisé, mets 4.
- Dans "steps", NE répète PAS les quantités chiffrées : réfère-toi aux ingrédients par leur nom, pour que l'ajustement des portions reste cohérent.
- "timerSeconds" : durée en secondes UNIQUEMENT si l'étape implique une attente (cuisson, repos, four). Sinon null.
- Le texte fourni est une transcription parlée : déduis les quantités et étapes au mieux, corrige les approximations orales ("genre deux trois oeufs" -> 3).
- Si aucune recette n'est trouvable, renvoie {"found": false}.`;

function extractVideoId(url) {
  if (!url) return null;
  const pats = [
    /youtu\.be\/([\w-]{11})/,
    /youtube\.com\/watch\?v=([\w-]{11})/,
    /youtube\.com\/shorts\/([\w-]{11})/,
    /youtube\.com\/embed\/([\w-]{11})/,
  ];
  for (const p of pats) { const m = url.match(p); if (m) return m[1]; }
  return null;
}

function isSupportedUrl(url) {
  return /(?:youtube\.com|youtu\.be|instagram\.com|tiktok\.com|vm\.tiktok\.com|facebook\.com|fb\.watch)/i.test(url || "");
}

// --- Transcript via Supadata (prend l'URL complète) ---
async function getTranscript(url) {
  if (!SUPADATA_KEY) return "";
  try {
    const r = await fetch(
      `https://api.supadata.ai/v1/transcript?url=${encodeURIComponent(url)}&text=true`,
      { headers: { "x-api-key": SUPADATA_KEY } }
    );
    if (!r.ok) return "";
    const d = await r.json();
    if (typeof d.content === "string") return d.content;
    if (Array.isArray(d.content)) return d.content.map((s) => s.text).join(" ");
    return "";
  } catch { return ""; }
}

// --- Description via YouTube Data API (optionnel) ---
async function getDescription(id) {
  if (!YT_KEY) return "";
  try {
    const r = await fetch(`https://www.googleapis.com/youtube/v3/videos?part=snippet&id=${id}&key=${YT_KEY}`);
    const d = await r.json();
    const sn = d.items?.[0]?.snippet;
    return sn ? `${sn.title}\n\n${sn.description}` : "";
  } catch { return ""; }
}

function extractJSON(text) {
  const t = text.replace(/```json/gi, "").replace(/```/g, "").trim();
  const a = t.indexOf("{"), b = t.lastIndexOf("}");
  if (a === -1 || b === -1) throw new Error("no json");
  return JSON.parse(t.slice(a, b + 1));
}

async function askClaude(source) {
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": ANTHROPIC_KEY,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 1500,
      messages: [{
        role: "user",
        content: `Voici le contenu d'une vidéo de recette (description et/ou transcription parlée). Structure-le.\n\n"""${source.slice(0, 14000)}"""\n\n${INSTRUCTIONS}`,
      }],
    }),
  });
  const data = await r.json();
  const text = (data.content || []).filter((b) => b.type === "text").map((b) => b.text).join("\n");
  return extractJSON(text);
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ found: false, error: "Méthode non autorisée" });
  try {
    const { url, text } = req.body || {};
    let source = "";
    let image = null;

    if (text && text.trim().length > 20) {
      source = text;
    } else {
      if (!isSupportedUrl(url)) return res.status(400).json({ found: false, error: "Lien non supporté (YouTube, Instagram, TikTok, Facebook)" });
      const ytId = extractVideoId(url); // non-null seulement pour YouTube
      if (ytId) image = `https://img.youtube.com/vi/${ytId}/hqdefault.jpg`;
      const [transcript, description] = await Promise.all([
        getTranscript(url),
        ytId ? getDescription(ytId) : Promise.resolve(""),
      ]);
      source = `${description}\n\nTRANSCRIPTION:\n${transcript}`.trim();
      if (source.replace("TRANSCRIPTION:", "").trim().length < 40) {
        return res.status(200).json({
          found: false,
          error: "Impossible de lire cette vidéo (pas de transcription disponible). Colle la description à la main.",
        });
      }
    }

    const recipe = await askClaude(source);
    if (recipe && recipe.found !== false) recipe.image = image;
    return res.status(200).json(recipe);
  } catch (e) {
    return res.status(200).json({ found: false, error: "Extraction impossible. Réessaie ou colle la description." });
  }
}
