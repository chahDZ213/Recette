// api/pay/webhook.js — Webhook Stripe (MODE TEST). À configurer dans le dashboard Stripe :
//   Développeurs → Webhooks → Ajouter un endpoint → https://<domaine>/api/pay/webhook
//   Événements : checkout.session.completed, customer.subscription.deleted
// puis coller le secret (whsec_…) dans STRIPE_WEBHOOK_SECRET (Vercel).
// La signature exige le corps BRUT → bodyParser désactivé.
import { cors, getStripe, setMisePremium } from "./_lib.js";

export const config = { api: { bodyParser: false } };

function rawBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

export default async function handler(req, res) {
  if (cors(req, res)) return;
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });

  const stripe = getStripe();
  const secret = process.env.STRIPE_WEBHOOK_SECRET || "";
  if (!stripe || !secret) return res.status(500).json({ error: "Webhook non configuré (STRIPE_WEBHOOK_SECRET manquante)" });

  let event;
  try {
    const buf = await rawBody(req);
    event = stripe.webhooks.constructEvent(buf, req.headers["stripe-signature"] || "", secret);
  } catch (e) {
    console.error("pay/webhook signature:", e && e.message);
    return res.status(400).json({ error: "Signature invalide" });
  }

  try {
    if (event.type === "checkout.session.completed") {
      const s = event.data.object;
      const md = s.metadata || {};
      if (md.app === "mise" && md.userId && (s.payment_status === "paid" || s.payment_status === "no_payment_required")) {
        await setMisePremium(md.userId, {
          active: true, plan: md.plan || null,
          stripe_session_id: s.id,
          stripe_customer_id: typeof s.customer === "string" ? s.customer : null,
        });
      }
    } else if (event.type === "customer.subscription.deleted") {
      const sub = event.data.object;
      const md = sub.metadata || {};
      if (md.app === "mise" && md.userId) {
        await setMisePremium(md.userId, { active: false });
      }
    }
  } catch (e) {
    // On loggue mais on répond 200 : Stripe rejouera sinon l'événement en boucle.
    console.error("pay/webhook traitement:", e && e.message);
  }
  return res.status(200).json({ received: true });
}
