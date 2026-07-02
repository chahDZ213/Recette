// api/schedule-push.js — planifie l'envoi d'une notification via QStash après un délai.
export const maxDuration = 30;

const QSTASH_URL = process.env.QSTASH_URL;        // ex: https://qstash-eu-central-1.upstash.io
const QSTASH_TOKEN = process.env.QSTASH_TOKEN;
const SEND_SECRET = process.env.SEND_SECRET;
const BASE_URL = process.env.PUBLIC_BASE_URL;     // ex: https://recette-xi.vercel.app

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });
  try {
    const { subscription, delaySeconds, title, body } = req.body || {};
    if (!subscription || !delaySeconds) return res.status(400).json({ error: "paramètres manquants" });

    const delay = Math.max(1, Math.min(86400, Math.round(delaySeconds))); // 1s .. 24h
    const dest = `${BASE_URL}/api/send-push`;

    const r = await fetch(`${QSTASH_URL}/v2/publish/${dest}`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${QSTASH_TOKEN}`,
        "Content-Type": "application/json",
        "Upstash-Delay": `${delay}s`,
      },
      body: JSON.stringify({ subscription, title, body, secret: SEND_SECRET }),
    });

    const d = await r.json().catch(() => ({}));
    if (!r.ok) return res.status(500).json({ error: "planification échouée", detail: d });
    return res.status(200).json({ id: d.messageId || d.messageID || null });
  } catch (e) {
    return res.status(500).json({ error: "erreur serveur" });
  }
}
