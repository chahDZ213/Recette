// api/extract.js — Fonction serverless Vercel (Node)
// Reçoit { url }, { text } ou { image } (data URL base64), renvoie une recette structurée en JSON.
// Transcript via Supadata (fiable depuis Vercel + fallback Whisper sur vidéos sans sous-titres).

export const maxDuration = 60;

const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;

/* Le modèle, réglable sans toucher au code.
   Opus 5 par défaut : la structuration d'une recette à partir d'une
   transcription parlée — retrouver les quantités, séparer les étapes,
   deviner ce qui est sous-entendu — est exactement ce qu'un modèle plus fin
   fait mieux. La variable permet de redescendre si la facture le demande. */
const MODELE = (process.env.MISE_CLAUDE_MODEL || "").trim() || "claude-opus-5";
const SUPADATA_KEY = process.env.SUPADATA_API_KEY;
const YT_KEY = process.env.YOUTUBE_API_KEY; // optionnel

/* ---------- Compte, premium et quotas ----------
   Chaque appel coûte de l'argent (Claude, puis OpenAI pour la photo). Trois
   garde-fous : il faut un compte, les fonctions payantes sont revérifiées
   dans premium_users (le drapeau du navigateur ne décide de rien), et un
   nombre d'appels par heure est plafonné. */
const SB_URL = process.env.SUPABASE_URL || "https://hpejfttwocclmqdtdiok.supabase.co";
const SB_ANON = process.env.SUPABASE_ANON_KEY || "sb_publishable_vXQvAJWpR0kKwQ-Fo9aWLw__0x3B7k5";

// Plafonds par compte et par heure glissante.
const LIMITS = { free: 20, premium: 120 };

/* Compteur en mémoire de l'instance. Une fonction serverless est recyclée et
   répliquée : ce plafond ne remplace pas un quota en base, mais il coupe net
   le cas qui coûte vraiment cher — une boucle qui martèle l'endpoint, servie
   par une instance déjà chaude. */
const hits = new Map(); // userId -> number[] (horodatages)
const WINDOW_MS = 3600_000;
function rateLimited(userId, max) {
  const now = Date.now();
  const list = (hits.get(userId) || []).filter((t) => now - t < WINDOW_MS);
  if (list.length >= max) { hits.set(userId, list); return true; }
  list.push(now);
  hits.set(userId, list);
  if (hits.size > 5000) { for (const k of hits.keys()) { hits.delete(k); if (hits.size <= 2500) break; } }
  return false;
}

async function supabaseUserId(req) {
  const jwt = (req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (!jwt) return null;
  try {
    const u = await fetch(SB_URL + "/auth/v1/user", {
      headers: { apikey: SB_ANON, authorization: "Bearer " + jwt },
    });
    if (!u.ok) return null;
    return (await u.json()).id || null;
  } catch { return null; }
}

// Lecture de premium_users avec la clé service_role : c'est la seule source
// de vérité. Sans clé configurée on renvoie null = « on ne sait pas ».
async function isPremiumUser(userId) {
  const svc = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  if (!svc || !userId) return null;
  try {
    const r = await fetch(
      `${SB_URL}/rest/v1/premium_users?user_id=eq.${encodeURIComponent(userId)}&select=active`,
      { headers: { apikey: svc, authorization: "Bearer " + svc } }
    );
    if (!r.ok) return null;
    const rows = await r.json();
    return Array.isArray(rows) && rows.length > 0 && rows[0].active === true;
  } catch { return null; }
}

/* ---------- Droit à l'effacement ----------
   Hébergé ici plutôt que dans sa propre fonction : le plan Vercel plafonne le
   nombre de fonctions serverless, et ce fichier porte déjà les autres actions
   liées au compte (code cadeau, traduction, idées). */
const BUCKET = "recipe-images";
function svcHeaders(extra) {
  const k = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  return Object.assign({ apikey: k, authorization: "Bearer " + k }, extra || {});
}
// Supprime les photos générées de la personne (préfixe gen/<uid>/).
async function deleteStoredPhotos(userId) {
  try {
    const list = await fetch(`${SB_URL}/storage/v1/object/list/${BUCKET}`, {
      method: "POST",
      headers: svcHeaders({ "content-type": "application/json" }),
      body: JSON.stringify({ prefix: `gen/${userId}`, limit: 1000 }),
    });
    if (!list.ok) return;
    const files = await list.json();
    const names = (Array.isArray(files) ? files : [])
      .map((f) => f && f.name).filter(Boolean)
      .map((n) => `gen/${userId}/${n}`);
    if (!names.length) return;
    await fetch(`${SB_URL}/storage/v1/object/${BUCKET}`, {
      method: "DELETE",
      headers: svcHeaders({ "content-type": "application/json" }),
      body: JSON.stringify({ prefixes: names }),
    });
  } catch (e) { console.error("compte/photos:", e && e.message); }
}
async function deleteRows(table, userId) {
  try {
    const r = await fetch(`${SB_URL}/rest/v1/${table}?user_id=eq.${encodeURIComponent(userId)}`, {
      method: "DELETE",
      headers: svcHeaders({ prefer: "return=minimal" }),
    });
    if (!r.ok) console.error("compte/" + table + ":", r.status, (await r.text()).slice(0, 200));
    return r.ok;
  } catch (e) { console.error("compte/" + table + ":", e && e.message); return false; }
}
// Efface photos, données puis le compte lui-même. Irréversible.
async function deleteAccount(userId) {
  await deleteStoredPhotos(userId);
  await deleteRows("shares", userId);
  await deleteRows("recipes", userId);
  await deleteRows("premium_users", userId);
  const del = await fetch(`${SB_URL}/auth/v1/admin/users/${encodeURIComponent(userId)}`, {
    method: "DELETE", headers: svcHeaders(),
  });
  if (!del.ok) {
    console.error("compte/auth:", del.status, (await del.text()).slice(0, 300));
    return false;
  }
  return true;
}

// Active le premium d'un compte (code cadeau) côté serveur, pour qu'il survive
// au changement d'appareil et passe les vérifications ci-dessus.
async function grantPremium(userId, plan) {
  const svc = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  if (!svc || !userId) return false;
  try {
    const r = await fetch(SB_URL + "/rest/v1/premium_users?on_conflict=user_id", {
      method: "POST",
      headers: {
        apikey: svc, authorization: "Bearer " + svc,
        "content-type": "application/json", prefer: "resolution=merge-duplicates",
      },
      body: JSON.stringify({ user_id: userId, active: true, plan, updated_at: new Date().toISOString() }),
    });
    return r.ok;
  } catch { return false; }
}

const INSTRUCTIONS = `Tu renvoies UNIQUEMENT un objet JSON, sans aucun texte autour, sans backticks. Format exact :
{
  "found": true,
  "title": "Nom du plat",
  "baseServings": 4,
  "ingredients": [{"name": "farine", "amount": 250, "unit": "g", "category": "Épicerie"}],
  "steps": [{"title": "Titre court", "content": "Instruction claire", "timerSeconds": 600, "temp": 180, "mode": "four"}],
  "imageQuery": "creamy chicken pasta"
}
Règles :
- "amount" est un nombre (ou null si non quantifiable). "unit" peut être null (ex: oeufs, gousses).
- "category" classe l'ingrédient dans EXACTEMENT une de ces valeurs : "Frais" (légumes, fruits, herbes fraîches, ail, oignon), "Viandes & poissons", "Crémerie" (oeufs, lait, beurre, fromage, crème, yaourt), "Épicerie" (pâtes, riz, farine, conserves, huile, sucre, produits secs), "Épices" (sel, poivre, épices, condiments, sauces), ou "Autre" si rien ne colle.
- "baseServings" = nombre de personnes/parts indiqué dans la recette d'origine. Si non précisé, mets 4.
- FIDÉLITÉ ABSOLUE AUX QUANTITÉS : recopie EXACTEMENT les chiffres donnés dans le texte (quantités, unités, nombre de personnes). N'adapte JAMAIS les quantités à un autre nombre de personnes que celui d'origine. Si la quantité d'un ingrédient n'est donnée nulle part, mets "amount": null — n'invente JAMAIS un chiffre plausible.
- Si une DESCRIPTION ÉCRITE et une transcription parlée divergent sur un chiffre, la description écrite fait foi.
- Dans "steps", NE répète PAS les quantités chiffrées : réfère-toi aux ingrédients par leur nom, pour que l'ajustement des portions reste cohérent.
- "timerSeconds" : durée en secondes UNIQUEMENT si l'étape implique une attente (cuisson, repos, four). Sinon null.
- "temp" : température de cuisson en °C (nombre entier) si l'étape en mentionne une (four à 180°C, four th.6, etc.). Convertis les thermostats en °C (th.6 ≈ 180). Sinon null.
- "mode" : mode de cuisson de l'étape, EXACTEMENT une de ces valeurs en minuscules sans accent : "four", "poele", "casserole", "friture", "vapeur", "micro-ondes", "grill", "barbecue", "repos". "repos" = attente sans cuisson (frigo, levée, marinade, refroidissement). Si l'étape est une simple préparation sans cuisson ni attente, mets null.
- "imageQuery" : 2 à 4 mots en ANGLAIS décrivant visuellement le plat fini (sert à chercher une photo). Toujours rempli. Exemples : "beef bourguignon stew", "chocolate lava cake".
- Si le texte fourni contient une transcription parlée : corrige les approximations orales ("genre deux trois oeufs" -> 3), mais seulement pour des quantités réellement mentionnées.
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

// --- Légende TikTok via oEmbed (la recette est souvent écrite dans la description, pas dite dans la vidéo) ---
async function getTikTokCaption(url) {
  if (!/tiktok\.com/i.test(url || "")) return "";
  try {
    let target = url;
    // les liens courts (vm.tiktok.com, /t/) redirigent vers l'URL canonique exigée par oEmbed
    if (/vm\.tiktok\.com|tiktok\.com\/t\//i.test(url)) {
      try {
        const ctrl = new AbortController();
        const to = setTimeout(() => ctrl.abort(), 6000);
        const r0 = await fetch(url, { redirect: "follow", signal: ctrl.signal, headers: { "user-agent": "Mozilla/5.0" } });
        clearTimeout(to);
        if (r0.url) target = r0.url;
      } catch {}
    }
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), 8000);
    const r = await fetch(`https://www.tiktok.com/oembed?url=${encodeURIComponent(target)}`, { signal: ctrl.signal });
    clearTimeout(to);
    if (!r.ok) return "";
    const d = await r.json();
    return (d && typeof d.title === "string") ? d.title.trim() : "";
  } catch { return ""; }
}

// --- Description via les balises og: de la page (Instagram, Facebook, TikTok…) ---
// Les réseaux sociaux servent la légende de la vidéo dans og:title / og:description
// même quand le reste de la page exige JavaScript ou une connexion.
async function getOgMeta(rawUrl, ua) {
  try {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), 8000);
    const r = await fetch(rawUrl, {
      redirect: "follow",
      signal: ctrl.signal,
      headers: {
        "user-agent": ua || "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "accept": "text/html,application/xhtml+xml",
        "accept-language": "fr-FR,fr;q=0.9,en;q=0.6",
      },
    });
    clearTimeout(to);
    if (!r.ok) return "";
    const html = (await r.text()).slice(0, 400000);
    const pick = (prop) => {
      const m = new RegExp(`<meta[^>]+(?:property|name)=["']${prop}["'][^>]*>`, "i").exec(html);
      if (!m) return "";
      const c = /content=["']([\s\S]*?)["']/i.exec(m[0]);
      return c ? c[1] : "";
    };
    const decode = (s) => s
      .replace(/&quot;/g, '"').replace(/&#x27;|&#39;|&apos;/g, "'")
      .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#(\d+);/g, (_, n) => String.fromCharCode(n))
      .replace(/&amp;/g, "&");
    const title = decode(pick("og:title") || "");
    const desc = decode(pick("og:description") || pick("twitter:description") || pick("description") || "");
    return [title, desc].filter(Boolean).join("\n").trim();
  } catch { return ""; }
}

// --- Dernier recours : page rendue par Supadata (quand les og: sont vides ou bloquées) ---
async function getWebScrape(url) {
  if (!SUPADATA_KEY) return "";
  try {
    const r = await fetch(`https://api.supadata.ai/v1/web/scrape?url=${encodeURIComponent(url)}`, {
      headers: { "x-api-key": SUPADATA_KEY },
    });
    if (!r.ok) return "";
    const d = await r.json();
    const c = d && (d.content || d.markdown || d.text);
    return typeof c === "string" ? c.slice(0, 8000).trim() : "";
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
      model: MODELE,
      max_tokens: 2200,
      // NOTE : pas de "temperature" ici — les modèles Claude 5 rejettent ce
      // paramètre (400). La fidélité vient des règles du prompt.
      messages: [{
        role: "user",
        content: `Voici le contenu d'une vidéo de recette (description et/ou transcription parlée). Structure-le.\n\n"""${source.slice(0, 14000)}"""\n\n${INSTRUCTIONS}`,
      }],
    }),
  });
  const data = await r.json();
  if (!r.ok || data.error) { console.error("extract/askClaude: erreur API", r.status, JSON.stringify(data.error || data).slice(0, 500)); throw new Error("api claude"); }
  const text = (data.content || []).filter((b) => b.type === "text").map((b) => b.text).join("\n");
  return extractJSON(text);
}

// --- Lecture d'une image (capture d'écran, photo d'un texte) via Claude vision ---
// Transforme une liste de data URLs en blocs image pour l'API.
function imageBlocks(list) {
  const blocks = [];
  for (const dataUrl of list) {
    const m = /^data:(image\/[a-zA-Z0-9.+-]+);base64,([\s\S]+)$/.exec(dataUrl || "");
    if (!m) continue;
    blocks.push({ type: "image", source: { type: "base64", media_type: m[1], data: m[2] } });
  }
  if (!blocks.length) throw new Error("image invalide");
  return blocks;
}

async function callVision(list, instruction, maxTokens) {
  const blocks = imageBlocks(list);
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": ANTHROPIC_KEY,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: MODELE,
      max_tokens: maxTokens || 2200,
      messages: [{ role: "user", content: [...blocks, { type: "text", text: instruction }] }],
    }),
  });
  const data = await r.json();
  if (!r.ok || data.error) { console.error("extract/vision: erreur API", r.status, JSON.stringify(data.error || data).slice(0, 500)); throw new Error("api claude"); }
  const text = (data.content || []).filter((b) => b.type === "text").map((b) => b.text).join("\n");
  return extractJSON(text);
}

/* Plusieurs images d'une même recette : titre sur l'une, ingrédients sur une
   autre, étapes sur une troisième — ou un commentaire qui porte la recette que
   la description ne donne pas. Elles sont lues ENSEMBLE, dans l'ordre reçu. */
async function askClaudeVision(list) {
  const n = list.length;
  const intro = n > 1
    ? `Ces ${n} images montrent UNE SEULE ET MÊME recette, en plusieurs morceaux et dans l'ordre (par exemple : le titre et la photo du plat, puis la liste des ingrédients, puis les étapes, ou encore un commentaire qui donne la recette). Lis-les toutes et combine-les en une seule recette complète. Ne produis PAS une recette par image. Si deux images se recouvrent, ne compte pas deux fois les mêmes ingrédients ou les mêmes étapes.`
    : `Cette image contient une recette de cuisine (capture d'écran, photo d'un texte, d'une page de livre ou d'une liste d'ingrédients). Lis tout son contenu et structure-le en recette.`;
  return callVision(list, `${intro}\n\n${INSTRUCTIONS}`, 2200);
}

/* Lecture d'une liste d'ingrédients seule, pour remplir les quantités d'une
   recette déjà importée. On ne renvoie QUE les ingrédients : le reste de la
   recette existe déjà et ne doit pas être réécrit. */
async function readIngredients(list) {
  const instruction = `Ces images montrent une liste d'ingrédients (capture d'écran, photo d'un livre, d'une étiquette ou d'un commentaire). Relève chaque ingrédient avec sa quantité.

Tu renvoies UNIQUEMENT un objet JSON, sans aucun texte autour, sans backticks. Format exact :
{"baseServings": 4, "ingredients": [{"name": "farine", "amount": 250, "unit": "g", "category": "Épicerie"}]}

Règles :
- "amount" est un nombre, ou null si la quantité n'est pas indiquée. N'INVENTE JAMAIS une quantité absente : mets null.
- Recopie EXACTEMENT les chiffres lus. "unit" peut être null (ex: oeufs, gousses).
- "category" vaut EXACTEMENT une de ces valeurs : "Frais", "Viandes & poissons", "Crémerie", "Épicerie", "Épices", "Autre".
- "baseServings" = nombre de personnes si les images l'indiquent, sinon null.
- Si aucune liste d'ingrédients n'est lisible, renvoie {"ingredients": []}.`;
  return callVision(list, instruction, 1600);
}

// --- Lecture d'une page web de recette (Marmiton, 750g, blogs...) ---
async function fetchWebText(rawUrl) {
  try {
    const url = (rawUrl || "").trim();
    if (!/^https?:\/\//i.test(url)) return null;
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), 10000);
    const r = await fetch(url, {
      headers: {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "accept": "text/html,application/xhtml+xml",
        "accept-language": "fr-FR,fr;q=0.9,en;q=0.6",
      },
      redirect: "follow",
      signal: ctrl.signal,
    });
    clearTimeout(to);
    if (!r.ok) return null;
    const html = (await r.text()).slice(0, 600000);
    // la photo du plat n'est plus extraite (og:image) : elle est générée par IA via /api/generate-image
    // données structurées schema.org Recipe (très fiables quand présentes)
    const lds = [];
    const re = /<script[^>]*application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi;
    let m;
    while ((m = re.exec(html))) { if (/recipe/i.test(m[1])) lds.push(m[1].trim()); }
    const ld = lds.join("\n").slice(0, 12000);
    // texte visible de la page
    const text = html
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/&nbsp;/gi, " ").replace(/&amp;/gi, "&").replace(/&#\d+;/g, " ").replace(/&[a-zA-Z]+;/g, " ")
      .replace(/\s+/g, " ").trim().slice(0, 12000);
    if (!ld && text.length < 100) return null;
    return {
      text: (ld ? "DONNEES STRUCTUREES (schema.org Recipe):\n" + ld + "\n\n" : "") + "TEXTE DE LA PAGE:\n" + text,
    };
  } catch (e) { return null; }
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
      model: MODELE,
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
    body: JSON.stringify({ model: MODELE, max_tokens: maxTokens || 700, messages: [{ role: "user", content: prompt }] }),
  });
  const data = await r.json();
  if (!r.ok || data.error) { console.error("extract/texte: erreur API", r.status, JSON.stringify(data.error || data).slice(0, 500)); throw new Error("api claude"); }
  const t = (data.content || []).filter((b) => b.type === "text").map((b) => b.text).join("\n");
  return extractJSON(t);
}

// liens copiés depuis les résultats Google : on récupère l'URL cible
function unwrapGoogleUrl(u) {
  if (typeof u !== "string") return u;
  if (!/^https?:\/\/(www\.)?google\.[a-z.]{2,10}\/url\?/i.test(u)) return u;
  try {
    const q = new URL(u).searchParams;
    const target = q.get("q") || q.get("url");
    if (target && /^https?:\/\//i.test(target)) return target;
  } catch {}
  return u;
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ found: false, error: "Méthode non autorisée" });
  // origine autorisée (opt-in : définir ALLOWED_ORIGINS="https://mon-app.vercel.app,https://…")
  const allowed = (process.env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (allowed.length) {
    const src = req.headers.origin || req.headers.referer || "";
    if (src && !allowed.some((a) => src.startsWith(a))) {
      return res.status(403).json({ found: false, error: "Origine non autorisée" });
    }
  }
  try {
    const body = req.body || {};
    let { url, text, image: imgInput } = body;
    // garde-fous sur la taille des entrées (protège la fonction et la facture API)
    if (typeof url === "string") { url = unwrapGoogleUrl(url.trim().slice(0, 2000)); }
    if (typeof text === "string") { text = text.slice(0, 30000); }
    /* Images : une seule (image) ou plusieurs (images[]). Vercel refuse les
       corps de requête au-delà de ~4,5 Mo, et le base64 gonfle de 33 % — d'où
       un plafond global volontairement en dessous. Le navigateur réduit déjà
       chaque photo avant l'envoi. */
    const MAX_IMAGES = 6, MAX_TOTAL = 3_600_000;
    let imgList = Array.isArray(body.images) ? body.images.filter((s) => typeof s === "string") : [];
    if (!imgList.length && typeof imgInput === "string" && imgInput.startsWith("data:image")) imgList = [imgInput];
    if (imgList.length > MAX_IMAGES) {
      return res.status(200).json({ found: false, error: `Trop de photos d'un coup (${MAX_IMAGES} au maximum).` });
    }
    if (imgList.reduce((n, s) => n + s.length, 0) > MAX_TOTAL) {
      return res.status(200).json({ found: false, error: "Photos trop lourdes au total. Réessaie avec moins de photos." });
    }

    /* ---- compte requis, premium vérifié, quota horaire ----
       Tout ce qui suit appelle un modèle payant. On exige donc un compte
       (un script anonyme ne peut plus faire tourner la facture), on
       revérifie le premium côté serveur pour les fonctions payantes, et on
       plafonne le nombre d'appels par heure. */
    const userId = await supabaseUserId(req);
    if (!userId) {
      return res.status(401).json({ found: false, error: "Connecte-toi pour utiliser cette fonction." });
    }
    const premium = await isPremiumUser(userId);

    // Droit à l'effacement (RGPD) : efface tout et supprime le compte.
    if (body.deleteAccount === true) {
      if (!process.env.SUPABASE_SERVICE_ROLE_KEY) {
        console.error("compte: SUPABASE_SERVICE_ROLE_KEY manquante");
        return res.status(501).json({ error: "Suppression non configurée sur ce serveur." });
      }
      const done = await deleteAccount(userId);
      return done
        ? res.status(200).json({ deleted: true })
        : res.status(502).json({ error: "Les données ont été effacées, mais le compte n'a pas pu être supprimé. Réessaie." });
    }

    // Code cadeau : validé puis enregistré côté serveur, pour qu'il suive le compte.
    if (body.redeemCode && typeof body.redeemCode === "string") {
      const codes = (process.env.PREMIUM_CODES || "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
      const ok = codes.includes(body.redeemCode.trim().toLowerCase());
      if (ok) await grantPremium(userId, "code");
      return res.status(200).json({ premiumOk: ok });
    }

    // Fonctions réservées au premium. premium === null = clé service_role
    // absente : on ne bloque pas sur une configuration incomplète.
    const wantsPremium = !!(body.ideas || body.fridge || body.create);
    if (wantsPremium && premium === false) {
      return res.status(402).json({ found: false, ideas: [], ingredients: "", error: "Cette fonction fait partie de mise. premium." });
    }

    if (rateLimited(userId, premium ? LIMITS.premium : LIMITS.free)) {
      return res.status(429).json({ found: false, ideas: [], ingredients: "", error: "Trop de demandes d'affilée. Réessaie dans quelques minutes." });
    }

    // 0.2) Traduction d'une recette existante vers la langue de l'app
    if (body.translate && body.recipe && typeof body.recipe === "object") {
      try {
        const target = body.lang === "en" ? "ANGLAIS" : "FRANÇAIS";
        const rec = JSON.stringify(body.recipe).slice(0, 20000);
        const prompt = `Traduis cette recette de cuisine en ${target}. Renvoie UNIQUEMENT l'objet JSON traduit, sans aucun texte autour, sans backticks, avec EXACTEMENT la même structure et les mêmes clés.
Règles :
- Traduis : "title", le "name" de chaque ingrédient, le "title" et le "content" de chaque étape, et "unit" seulement si c'est un mot ("c. à s." <-> "tbsp", "pincée" <-> "pinch" ; laisse "g", "ml", "cl", "kg" tels quels).
- NE CHANGE PAS : les nombres ("amount", "baseServings", "timerSeconds", "temp"), "mode", "category" (clés internes, toujours en français), "imageQuery", ni l'ordre des éléments.
- Si la recette est déjà entièrement dans la langue cible, renvoie-la telle quelle.

RECETTE :
${rec}`;
        const out = await askClaudeText(prompt, 2500);
        if (!out || !out.title || !Array.isArray(out.ingredients) || !Array.isArray(out.steps)) throw new Error("traduction invalide");
        out.found = true;
        return res.status(200).json(out);
      } catch (e) {
        return res.status(200).json({ found: false, error: "Traduction impossible. Réessaie." });
      }
    }

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

    // 0.4) Le code premium est traité plus haut (il exige un compte et s'enregistre en base).

    // 0.5) Photo de frigo/placard -> liste d'ingrédients (pour l'écran Idées)
    if (body.fridge && typeof body.fridge === "string" && body.fridge.startsWith("data:image")) {
      try {
        const ingredients = await readFridge(body.fridge);
        return res.status(200).json({ ingredients });
      } catch (e) {
        return res.status(200).json({ ingredients: "", error: "Impossible de lire cette photo." });
      }
    }

    // 0.6) Photo(s) d'une liste d'ingrédients -> remplit une recette existante
    if (body.readIngredients === true) {
      if (!imgList.length) return res.status(200).json({ ingredients: [], error: "Aucune photo reçue." });
      try {
        const out = await readIngredients(imgList);
        const list = Array.isArray(out && out.ingredients) ? out.ingredients : [];
        return res.status(200).json({ ingredients: list, baseServings: (out && out.baseServings) || null });
      } catch (e) {
        console.error("extract/ingredients:", e && e.message);
        return res.status(200).json({ ingredients: [], error: "Je n'ai pas réussi à lire cette liste. Essaie une photo plus nette." });
      }
    }

    // 1) Image(s) (captures d'écran / photos d'un texte) -> Claude vision
    if (imgList.length) {
      const recipe = await askClaudeVision(imgList);
      return res.status(200).json(recipe);
    }

    let source = "";

    if (text && text.trim().length > 20) {
      source = text;
    } else if (!isSupportedUrl(url)) {
      // site web de recette classique (Marmiton, 750g, blogs...)
      const web = await fetchWebText(url);
      if (!web) {
        return res.status(200).json({ found: false, error: "Impossible de lire cette page. Colle le texte de la recette à la main." });
      }
      source = web.text;
    } else {
      const ytId = extractVideoId(url); // non-null seulement pour YouTube
      const [transcript, ytDescription, tiktokCaption, ogMeta] = await Promise.all([
        getTranscript(url),
        ytId ? getDescription(ytId) : Promise.resolve(""),
        getTikTokCaption(url),
        getOgMeta(url),
      ]);
      // Facebook/Instagram servent souvent une page de connexion aux navigateurs
      // inconnus mais donnent toujours les og: à leur propre crawler : 2e tentative.
      let og = ogMeta;
      if (!og && /facebook\.com|fb\.watch|instagram\.com/i.test(url)) {
        og = await getOgMeta(url, "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)");
      }
      // on garde chaque source écrite, sans doublons (la légende TikTok réapparaît souvent dans les og:)
      const parts = [ytDescription, tiktokCaption, og].map((s) => (s || "").trim()).filter(Boolean);
      const uniq = parts.filter((p, i) => !parts.some((q, j) => j !== i && q.includes(p) && (q.length > p.length || j < i)));
      const description = uniq.join("\n\n");
      // aucune description trouvée (même avec de l'audio) -> page rendue en dernier recours :
      // la recette écrite dans la légende vaut mieux que la seule transcription parlée
      const pageDump = description ? "" : await getWebScrape(url);
      source = [
        description ? "DESCRIPTION ÉCRITE (publiée par l'auteur — fait foi pour les quantités et le nombre de personnes):\n" + description : "",
        pageDump ? "CONTENU DE LA PAGE (extrait automatique, peut contenir du bruit ; si la recette y est écrite, ses chiffres font foi):\n" + pageDump : "",
        transcript.trim() ? "TRANSCRIPTION PARLÉE:\n" + transcript : "",
      ].filter(Boolean).join("\n\n");
      if ((description + pageDump + transcript).trim().length < 40) {
        return res.status(200).json({
          found: false,
          error: "Impossible de lire cette vidéo (ni transcription ni description accessibles). Colle la recette à la main.",
        });
      }
    }

    if (body.lang === "en" && source) {
      source = 'IMPORTANT: Write ALL recipe content (title, ingredients names, steps, imageQuery) in ENGLISH, but keep the "category" field values in French exactly as listed in the schema (they are internal keys).\n\n' + source;
    }
    const recipe = await askClaude(source);
    // recipe.image reste vide : la photo est générée par IA côté front via /api/generate-image
    return res.status(200).json(recipe);
  } catch (e) {
    console.error("extract: échec", e && e.message, e && e.stack ? e.stack.split("\n")[1] : "");
    return res.status(200).json({ found: false, error: "Extraction impossible. Réessaie ou colle la description." });
  }
}
