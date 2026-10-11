// api/pay/portal.js — Ouvre le portail client Stripe : la personne y résilie,
// change de carte et retrouve ses factures elle-même. C'est une obligation,
// pas un confort : un abonnement doit pouvoir être arrêté sans passer par toi.
//
// POST { returnUrl } avec le jeton Supabase dans Authorization → { url }.
// L'identifiant client Stripe est lu dans premium_users (écrit par le webhook).
//
// Prérequis Stripe : le portail doit avoir été configuré une fois dans le
// dashboard (Paramètres → Facturation → Portail client). Sinon Stripe refuse
// la création et on renvoie un message explicite.
import { cors, getStripe, safeReturnUrl, supabaseUserId, SB_URL } from "./_lib.js";

async function stripeCustomerId(userId) {
  const svc = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  if (!svc) return null;
  try {
    const r = await fetch(
      `${SB_URL}/rest/v1/premium_users?user_id=eq.${encodeURIComponent(userId)}&select=stripe_customer_id`,
      { headers: { apikey: svc, authorization: "Bearer " + svc } }
    );
    if (!r.ok) return null;
    const rows = await r.json();
    return (Array.isArray(rows) && rows[0] && rows[0].stripe_customer_id) || null;
  } catch { return null; }
}

export default async function handler(req, res) {
  if (cors(req, res)) return;
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });

  const stripe = getStripe();
  if (!stripe) return res.status(500).json({ error: "Paiement non configuré (STRIPE_SECRET_KEY manquante)" });

  const userId = await supabaseUserId(req);
  if (!userId) return res.status(401).json({ error: "Connexion requise" });

  const customer = await stripeCustomerId(userId);
  if (!customer) {
    return res.status(404).json({ error: "Aucun abonnement trouvé sur ce compte." });
  }

  const fallback = (process.env.PUBLIC_BASE_URL || "https://recette-xi.vercel.app").replace(/\/$/, "") + "/";
  const returnUrl = safeReturnUrl(req.body && req.body.returnUrl, fallback);

  try {
    const session = await stripe.billingPortal.sessions.create({ customer, return_url: returnUrl });
    return res.status(200).json({ url: session.url });
  } catch (e) {
    console.error("pay/portal:", e && e.message);
    return res.status(502).json({ error: "Le portail de gestion n'est pas disponible pour le moment." });
  }
}
