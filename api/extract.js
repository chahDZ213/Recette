// api/extract.js — Fonction serverless Vercel (Node)
// Reçoit { url }, { text } ou { image } (data URL base64), renvoie une recette structurée en JSON.
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
  "ingredients": [{"name": "farine", "amount": 250, "unit": "g", "category": "Épicerie"}],
  "steps": [{"title": "Titre court", "content": "Instruction claire", "timerSeconds": 600, "temp": 180, "mode": "four"}]
}
Règles :
- "amount" est un nombre (ou null si non quantifiable). "unit" peut être null (ex: oeufs, gousses).
- "category" classe l'ingrédient dans EXACTEMENT une de ces valeurs : "Frais" (légumes, fruits, herbes fraîches, ail, oignon), "Viandes & poissons", "Crémerie" (oeufs, lait, beurre, fromage, crème, yaourt), "Épicerie" (pâtes, riz, farine, conserves, huile, sucre, produits secs), "Épices" (sel, poivre, épices, condiments, sauces), ou "Autre" si rien ne colle.
- "baseServings" = nombre de personnes de la recette d'origine. Si non précisé, mets 4.
- Dans "steps", NE répète PAS les quantités chiffrées : réfère-toi aux ingrédients par leur nom, pour que l'ajustement des portions reste cohérent.
- "timerSeconds" : durée en secondes UNIQUEMENT si l'étape implique une attente (cuisson, repos, four). Sinon null.
- "temp" : température de cuisson en °C (nombre entier) si l'étape en mentionne une (four à 180°C, four th.6, etc.). Convertis les thermostats en °C (th.6 ≈ 180). Sinon null.
- "mode" : mode de cuisson de l'étape, EXACTEMENT une de ces valeurs en minuscules sans accent : "four", "poele", "casserole", "friture", "vapeur", "micro-ondes", "grill", "barbecue", "repos". "repos" = attente sans cuisson (frigo, levée, marinade, refroidissement). Si l'étape est une simple préparation sans cuisson ni attente, mets null.
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

// --- Lecture d'une image (capture d'écran, photo d'un texte) via Claude vision ---
async function askClaudeVision(dataUrl) {
  const m = /^data:(image\/[a-zA-Z0-9.+-]+);base64,([\s\S]+)$/.exec(dataUrl || "");
  if (!m) throw new Error("image invalide");
  const mediaType = m[1], b64 = m[2];
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
        content: [
          { type: "image", source: { type: "base64", media_type: mediaType, data: b64 } },
          { type: "text", text: `Cette image contient une recette de cuisine (capture d'écran, photo d'un texte, d'une page de livre ou d'une liste d'ingrédients). Lis tout son contenu et structure-le en recette.\n\n${INSTRUCTIONS}` },
        ],
      }],
    }),
  });
  const data = await r.json();
  const text = (data.content || []).filter((b) => b.type === "text").map((b) => b.text).join("\n");
  return extractJSON(text);
}

// --- Lecture d'une photo de frigo/placard -> liste d'ingrédients ---
async function readFridge(dataUrl) {
  const m = /^data:(image\/[a-zA-Z0-9.+-]+);base64,([\s\S]+)$/.exec(dataUrl || "");
  if (!m) throw new Error("image invalide");
  const mediaType = m[1], b64 = m[2];
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": ANTHROPIC_KEY,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 400,
      messages: [{
        role: "user",
        content: [
          { type: "image", source: { type: "base64", media_type: mediaType, data: b64 } },
          { type: "text", text: `Cette photo montre l'intérieur d'un frigo, d'un placard ou un plan de travail avec des aliments. Liste UNIQUEMENT les ingrédients alimentaires que tu identifies clairement, séparés par des virgules, en français, au singulier, sans quantités ni marques. Ignore les objets non alimentaires et ce qui est trop flou pour être sûr. Réponds SEULEMENT par la liste, rien d'autre (pas de phrase, pas de puces, pas de backticks). Exemple : oeufs, lait, tomates, carottes, fromage, beurre. Si tu ne reconnais aucun aliment, réponds exactement : (aucun)` },
        ],
      }],
    }),
  });
  const data = await r.json();
  let txt = (data.content || []).filter((b) => b.type === "text").map((b) => b.text).join(" ").trim();
  txt = txt.replace(/^["'\s]+|["'\s]+$/g, "").replace(/```/g, "").trim();
  if (/^\(?\s*aucun\s*\)?\.?$/i.test(txt)) return "";
  return txt;
}

async function askClaudeText(prompt, maxTokens) {
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "content-type": "application/json", "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01" },
    body: JSON.stringify({ model: "claude-sonnet-4-6", max_tokens: maxTokens || 700, messages: [{ role: "user", content: prompt }] }),
  });
  const data = await r.json();
  const t = (data.content || []).filter((b) => b.type === "text").map((b) => b.text).join("\n");
  return extractJSON(t);
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ found: false, error: "Méthode non autorisée" });
  try {
    const body = req.body || {};
    const { url, text, image: imgInput } = body;

    // 0) Idées "frigo" -> liste de suggestions à partir d'ingrédients
    if (body.ideas) {
      const ing = (body.ingredients || "").slice(0, 400);
      const type = body.type || "";
      const cons = [body.quick ? "très rapide (moins de 20 min)" : null, body.cheap ? "pas cher / économique" : null].filter(Boolean).join(", ");
      const prompt = `Propose 4 idées de recettes ${type} réalistes et simples, en utilisant SURTOUT ces ingrédients que la personne a chez elle : ${ing || "(non précisé)"}.${cons ? " Contraintes : " + cons + "." : ""}
On peut supposer qu'elle a des basiques (sel, poivre, huile, eau, farine).
Renvoie UNIQUEMENT un objet JSON, sans texte ni backticks, format exact :
{"ideas":[{"title":"Nom du plat","desc":"description en une phrase","time":"15 min"}]}
Exactement 4 idées, variées.`;
      try {
        const out = await askClaudeText(prompt, 700);
        return res.status(200).json({ ideas: (out && out.ideas) || [] });
      } catch (e) {
        return res.status(200).json({ ideas: [], error: "Impossible de générer des idées." });
      }
    }

    // 0.5) Photo de frigo/placard -> liste d'ingrédients (pour l'écran Idées)
    if (body.fridge && typeof body.fridge === "string" && body.fridge.startsWith("data:image")) {
      try {
        const ingredients = await readFridge(body.fridge);
        return res.status(200).json({ ingredients });
      } catch (e) {
        return res.status(200).json({ ingredients: "", error: "Impossible de lire cette photo." });
      }
    }

    // 1) Image (capture d'écran / photo d'un texte) -> Claude vision
    if (imgInput && typeof imgInput === "string" && imgInput.startsWith("data:image")) {
      const recipe = await askClaudeVision(imgInput);
      return res.status(200).json(recipe); // pas de photo de plat auto ici
    }

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
