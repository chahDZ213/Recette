// api/extract.js â€” Fonction serverless Vercel (Node)
// ReÃ§oit { url } ou { text }, renvoie une recette structurÃ©e en JSON.
import { YoutubeTranscript } from "youtube-transcript";

const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;
const YT_KEY = process.env.YOUTUBE_API_KEY; // optionnel mais recommandÃ©

const INSTRUCTIONS = `Tu renvoies UNIQUEMENT un objet JSON, sans aucun texte autour, sans backticks. Format exact :
{
  "found": true,
  "title": "Nom du plat",
  "baseServings": 4,
  "ingredients": [{"name": "farine", "amount": 250, "unit": "g"}],
  "steps": [{"title": "Titre court", "content": "Instruction claire", "timerSeconds": 600}]
}
RÃ¨gles :
- "amount" est un nombre (ou null si non quantifiable). "unit" peut Ãªtre null (ex: oeufs, gousses).
- "baseServings" = nombre de personnes de la recette d'origine. Si non prÃ©cisÃ©, mets 4.
- Dans "steps", NE rÃ©pÃ¨te PAS les quantitÃ©s chiffrÃ©es : rÃ©fÃ¨re-toi aux ingrÃ©dients par leur nom, pour que l'ajustement des portions reste cohÃ©rent.
- "timerSeconds" : durÃ©e en secondes UNIQUEMENT si l'Ã©tape implique une attente (cuisson, repos, four). Sinon null.
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

async function getTranscript(id) {
  try {
    const items = await YoutubeTranscript.fetchTranscript(id, { lang: "fr" })
      .catch(() => YoutubeTranscript.fetchTranscript(id));
    return items.map((i) => i.text).join(" ");
  } catch { return ""; }
}

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
        content: `Voici le contenu d'une vidÃ©o de recette (description et/ou sous-titres). Structure-le.\n\n"""${source.slice(0, 12000)}"""\n\n${INSTRUCTIONS}`,
      }],
    }),
  });
  const data = await r.json();
  const text = (data.content || []).filter((b) => b.type === "text").map((b) => b.text).join("\n");
  return extractJSON(text);
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ found: false, error: "MÃ©thode non autorisÃ©e" });
  try {
    const { url, text } = req.body || {};
    let source = "";

    if (text && text.trim().length > 20) {
      source = text;
    } else {
      const id = extractVideoId(url);
      if (!id) return res.status(400).json({ found: false, error: "Lien YouTube invalide" });
      const [transcript, description] = await Promise.all([getTranscript(id), getDescription(id)]);
      source = `${description}\n\nTRANSCRIPTION:\n${transcript}`.trim();
      if (source.replace("TRANSCRIPTION:", "").trim().length < 40) {
        return res.status(200).json({
          found: false,
          error: "Pas de sous-titres ni de description exploitables pour cette vidÃ©o. Colle la description Ã  la main.",
        });
      }
    }

    const recipe = await askClaude(source);
    return res.status(200).json(recipe);
  } catch (e) {
    return res.status(200).json({ found: false, error: "Extraction impossible. RÃ©essaie ou colle la description." });
  }
}
