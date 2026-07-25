// api/budget-push.js — appelé chaque jour par QStash : calcule les échéances du jour
// et envoie la notification push. Protégé par SEND_SECRET (jamais transmis par le client :
// c'est api/budget-schedule.js qui l'injecte au moment de créer la planification).
import webpush from "web-push";
import { todayLocal } from "./_budget-core.js";
import { composeNotification } from "./_budget-notify.js";

const VAPID_PUBLIC = process.env.VAPID_PUBLIC_KEY;
const VAPID_PRIVATE = process.env.VAPID_PRIVATE_KEY;
const SEND_SECRET = process.env.SEND_SECRET;

if (VAPID_PUBLIC && VAPID_PRIVATE) {
  webpush.setVapidDetails("mailto:contact@mise.app", VAPID_PUBLIC, VAPID_PRIVATE);
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();
  try {
    const data = req.body || {};
    if (data.secret !== SEND_SECRET) return res.status(401).json({ error: "non autorisé" });
    if (!data.subscription) return res.status(400).json({ error: "pas d'abonnement" });

    const today = todayLocal(Number(data.tzOffset || 0));
    const notif = composeNotification(data, today);
    if (!notif) return res.status(200).json({ ok: true, skipped: "rien à signaler" });

    await webpush.sendNotification(
      data.subscription,
      JSON.stringify({ title: notif.title, body: notif.body, tag: "echeance-jour", url: "/budget/" })
    );
    return res.status(200).json({ ok: true });
  } catch (e) {
    // 200 malgré l'erreur : sinon QStash retente en boucle sur un abonnement expiré.
    return res.status(200).json({ ok: false, error: String((e && e.message) || e) });
  }
}
