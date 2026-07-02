// api/cancel-push.js — annule un push planifié (si le minuteur est mis en pause / relancé / quitté).
export const maxDuration = 15;

const QSTASH_URL = process.env.QSTASH_URL;
const QSTASH_TOKEN = process.env.QSTASH_TOKEN;

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });
  try {
    const { id } = req.body || {};
    if (!id) return res.status(400).json({ error: "id manquant" });
    await fetch(`${QSTASH_URL}/v2/messages/${id}`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${QSTASH_TOKEN}` },
    });
    return res.status(200).json({ ok: true });
  } catch (e) {
    return res.status(200).json({ ok: false });
  }
}
