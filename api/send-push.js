// api/send-push.js — reçu par QStash après le délai : envoie la notification web push.
import webpush from "web-push";

const VAPID_PUBLIC = process.env.VAPID_PUBLIC_KEY;
const VAPID_PRIVATE = process.env.VAPID_PRIVATE_KEY;
const SEND_SECRET = process.env.SEND_SECRET;

if (VAPID_PUBLIC && VAPID_PRIVATE) {
  webpush.setVapidDetails("mailto:contact@mise.app", VAPID_PUBLIC, VAPID_PRIVATE);
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();
  try {
    const { subscription, title, body, secret } = req.body || {};
    if (secret !== SEND_SECRET) return res.status(401).json({ error: "non autorisé" });
    if (!subscription) return res.status(400).json({ error: "pas d'abonnement" });

    await webpush.sendNotification(
      subscription,
      JSON.stringify({ title: title || "mise.", body: body || "⏲️ Ton minuteur est terminé !", tag: "mise-timer" })
    );
    return res.status(200).json({ ok: true });
  } catch (e) {
    // 200 quand même pour éviter que QStash retente en boucle si l'abonnement est expiré
    return res.status(200).json({ ok: false, error: String((e && e.message) || e) });
  }
}
