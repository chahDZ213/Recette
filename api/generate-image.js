// api/generate-image.js — Génération d'une photo IA pour une recette (OpenAI Images) + upload Supabase Storage.
// Reçoit { recipeId, title, imageQuery, ingredients }, renvoie { url } (URL publique Storage).
// Protections : méthode POST, ALLOWED_ORIGINS, JWT Supabase obligatoire (l'upload se fait avec le JWT
// de l'utilisateur : les policies Storage garantissent qu'il n'écrit que dans gen/{son_uid}/).
// La clé OpenAI ne vit que côté serveur. Modèle et qualité pilotés par IMAGE_MODEL / IMAGE_QUALITY.
export const maxDuration = 60;

const SB_URL = process.env.SUPABASE_URL || "https://hpejfttwocclmqdtdiok.supabase.co";
// clé publishable (déjà publique dans le front) — sert uniquement d'apikey pour valider le JWT et uploader
const SB_KEY = process.env.SUPABASE_ANON_KEY || "sb_publishable_vXQvAJWpR0kKwQ-Fo9aWLw__0x3B7k5";
const BUCKET = "recipe-images";

async function openaiImage(prompt, model, quality) {
  const r = await fetch("https://api.openai.com/v1/images/generations", {
    method: "POST",
    headers: {
      authorization: "Bearer " + process.env.OPENAI_API_KEY,
      "content-type": "application/json",
    },
    // output_compression : recompression WebP par OpenAI (0-100). ~55 vise 150-250 Ko par image
    // (sans lui : ~1,1 Mo). Ajustable via IMAGE_COMPRESSION sans toucher au code.
    body: JSON.stringify({
      model, prompt, size: "1024x1024", quality,
      output_format: "webp",
      output_compression: Math.min(100, Math.max(0, parseInt(process.env.IMAGE_COMPRESSION || "55", 10) || 55)),
    }),
  });
  if (!r.ok) {
    const err = new Error("openai " + r.status);
    err.status = r.status;
    err.body = (await r.text()).slice(0, 500);
    throw err;
  }
  const d = await r.json();
  const b64 = d.data && d.data[0] && d.data[0].b64_json;
  if (!b64) throw new Error("openai: réponse sans image");
  return { buf: Buffer.from(b64, "base64"), usage: d.usage || null };
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });

  // origine autorisée (même logique que api/extract.js)
  const allowed = (process.env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (allowed.length) {
    const src = req.headers.origin || req.headers.referer || "";
    if (src && !allowed.some((a) => src.startsWith(a))) {
      return res.status(403).json({ error: "Origine non autorisée" });
    }
  }

  // utilisateur connecté obligatoire : on valide le JWT Supabase auprès de l'API auth
  const jwt = (req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (!jwt) return res.status(401).json({ error: "Connexion requise" });
  let userId = null;
  try {
    const u = await fetch(SB_URL + "/auth/v1/user", {
      headers: { apikey: SB_KEY, authorization: "Bearer " + jwt },
    });
    if (!u.ok) return res.status(401).json({ error: "Session invalide ou expirée" });
    userId = (await u.json()).id;
  } catch {
    return res.status(401).json({ error: "Session invalide ou expirée" });
  }
  if (!userId) return res.status(401).json({ error: "Session invalide ou expirée" });

  if (!process.env.OPENAI_API_KEY) {
    return res.status(500).json({ error: "Génération d'images non configurée (OPENAI_API_KEY manquante)" });
  }

  const body = req.body || {};
  const recipeId = typeof body.recipeId === "string" ? body.recipeId.slice(0, 80) : "";
  const title = typeof body.title === "string" ? body.title.slice(0, 200).trim() : "";
  const imageQuery = typeof body.imageQuery === "string" ? body.imageQuery.slice(0, 120).trim() : "";
  const ingredients = Array.isArray(body.ingredients)
    ? body.ingredients.filter((x) => typeof x === "string").slice(0, 5).map((x) => x.slice(0, 60))
    : [];
  if (!/^[a-zA-Z0-9-]{6,80}$/.test(recipeId)) return res.status(400).json({ error: "recipeId invalide" });
  if (!title) return res.status(400).json({ error: "titre manquant" });

  const model = process.env.IMAGE_MODEL || "gpt-image-2";
  const quality = process.env.IMAGE_QUALITY || "low";
  const prompt =
    `Professional food photography of ${title}` +
    (imageQuery ? ` (${imageQuery})` : "") +
    (ingredients.length ? `, featuring ${ingredients.join(", ")}` : "") +
    ". Natural light, appetizing plating on a beautiful dish, realistic, shallow depth of field, premium but authentic home-cooked look. No text, no hands, no people.";

  try {
    // 1 retry sur erreur transitoire (429 / 5xx)
    let img;
    try {
      img = await openaiImage(prompt, model, quality);
    } catch (e) {
      if (e.status === 429 || (e.status >= 500 && e.status < 600)) {
        await new Promise((r2) => setTimeout(r2, 2500));
        img = await openaiImage(prompt, model, quality);
      } else throw e;
    }

    // upload Storage avec le JWT de l'utilisateur (policies : uniquement gen/{son_uid}/…)
    const path = `gen/${userId}/${recipeId}/${Date.now()}.webp`;
    const up = await fetch(`${SB_URL}/storage/v1/object/${BUCKET}/${path}`, {
      method: "POST",
      headers: { apikey: SB_KEY, authorization: "Bearer " + jwt, "content-type": "image/webp" },
      body: img.buf,
    });
    if (!up.ok) {
      const t = (await up.text()).slice(0, 300);
      return res.status(502).json({ error: "Échec de la sauvegarde de l'image", detail: t });
    }
    return res.status(200).json({
      url: `${SB_URL}/storage/v1/object/public/${BUCKET}/${path}`,
      model,
      quality,
      usage: img.usage,
    });
  } catch (e) {
    if (e.status === 429) return res.status(429).json({ error: "Quota d'images atteint, réessaie dans un instant" });
    return res.status(502).json({ error: "La génération d'image a échoué", detail: String(e.body || e.message || e).slice(0, 300) });
  }
}
