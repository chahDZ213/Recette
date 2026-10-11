// api/pay/webhook.js — Webhook Stripe (MODE TEST). À configurer dans le dashboard Stripe :
//   Développeurs → Webhooks → Ajouter un endpoint → https://<domaine>/api/pay/webhook
//   Événements : checkout.session.completed, customer.subscription.deleted
// puis coller le secret (whsec_…) dans STRIPE_WEBHOOK_SECRET (Vercel).
// La signature exige le corps BRUT → bodyParser désactivé.
import { cors, getStripe, setMisePremium } from "./_lib.js";

export const config = { api: { bodyParser: false } };

// Mémoire courte des événements déjà traités (voir la note sur l'idempotence
// dans le handler). Bornée pour ne pas grossir indéfiniment.
const seen = new Set();
function remember(id) {
  seen.add(id);
  if (seen.size > 2000) { for (const k of seen) { seen.delete(k); if (seen.size <= 1000) break; } }
}

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

  /* Idempotence. Stripe rejoue le même événement : chaque branche ci-dessous
     écrit un ÉTAT absolu (active vrai ou faux) par un upsert, jamais un
     incrément — rejouer un événement redonne donc exactement le même
     résultat. Le garde ci-dessous évite seulement le travail inutile quand
     le rejeu retombe sur une instance déjà chaude. */
  if (seen.has(event.id)) return res.status(200).json({ received: true, duplicate: true });
  remember(event.id);

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
    } else if (event.type === "invoice.paid") {
      // Renouvellement réussi : on réactive (couvre le cas d'un compte suspendu
      // après un échec, puis régularisé).
      const inv = event.data.object;
      const md = (inv.subscription_details && inv.subscription_details.metadata) || inv.metadata || {};
      if (md.app === "mise" && md.userId) {
        await setMisePremium(md.userId, {
          active: true, plan: md.plan || null,
          stripe_customer_id: typeof inv.customer === "string" ? inv.customer : null,
        });
      }
    } else if (event.type === "invoice.payment_failed") {
      /* Échec de paiement. Stripe relance plusieurs fois (Smart Retries) ; on
         ne coupe l'accès qu'au moment où il abandonne, c'est-à-dire quand
         l'abonnement n'est plus ni actif ni en période d'essai. */
      const inv = event.data.object;
      const md = (inv.subscription_details && inv.subscription_details.metadata) || inv.metadata || {};
      if (md.app === "mise" && md.userId) {
        let status = "";
        try {
          if (typeof inv.subscription === "string") {
            status = (await stripe.subscriptions.retrieve(inv.subscription)).status || "";
          }
        } catch (e) { console.error("pay/webhook sub:", e && e.message); }
        if (status && status !== "active" && status !== "trialing") {
          await setMisePremium(md.userId, { active: false, plan: md.plan || null });
        }
      }
    } else if (event.type === "customer.subscription.updated") {
      // L'état de l'abonnement fait foi : pause, impayé définitif, reprise.
      const sub = event.data.object;
      const md = sub.metadata || {};
      if (md.app === "mise" && md.userId) {
        const live = sub.status === "active" || sub.status === "trialing";
        await setMisePremium(md.userId, {
          active: live, plan: md.plan || null,
          stripe_customer_id: typeof sub.customer === "string" ? sub.customer : null,
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
