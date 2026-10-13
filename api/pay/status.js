// api/pay/status.js — Deux usages sur un même endpoint, pour tenir dans le
// plafond de fonctions du plan Vercel :
//   GET  ?session_id=cs_…  → état d'une session Checkout { paid, app, plan }.
//                            Si elle est payée et concerne mise., active aussi
//                            le premium côté serveur (filet de sécurité si le
//                            webhook n'est pas encore configuré — l'écriture
//                            est idempotente, webhook et endpoint visent la
//                            même ligne).
//   POST { returnUrl }     → ouvre le portail client Stripe : résiliation et
//                            changement de carte en autonomie. C'est une
//                            obligation, pas un confort. Jeton Supabase requis.
//
// Prérequis portail : il doit avoir été configuré une fois dans le dashboard
// Stripe (Paramètres → Facturation → Portail client).
import { cors, getStripe, safeReturnUrl, setMisePremium, supabaseUserId, SB_URL } from "./_lib.js";

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

  const stripe = getStripe();
  if (!stripe) return res.status(500).json({ error: "Paiement non configuré (STRIPE_SECRET_KEY manquante)" });

  // ---- POST : portail client ----
  if (req.method === "POST") {
    const userId = await supabaseUserId(req);
    if (!userId) return res.status(401).json({ error: "Connexion requise" });
    const customer = await stripeCustomerId(userId);
    if (!customer) return res.status(404).json({ error: "Aucun abonnement trouvé sur ce compte." });
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

  // ---- GET : état d'une session Checkout ----
  if (req.method !== "GET") return res.status(405).json({ error: "Méthode non autorisée" });

  const id = typeof req.query.session_id === "string" ? req.query.session_id : "";
  if (!/^cs_(test|live)_[A-Za-z0-9]+$/.test(id)) return res.status(400).json({ error: "session_id invalide" });

  try {
    const s = await stripe.checkout.sessions.retrieve(id);
    const paid = s.payment_status === "paid" || s.payment_status === "no_payment_required";
    const app = (s.metadata && s.metadata.app) || "";
    const plan = (s.metadata && s.metadata.plan) || "";

    if (paid && app === "mise" && s.metadata.userId) {
      await setMisePremium(s.metadata.userId, {
        active: true, plan,
        stripe_session_id: s.id,
        stripe_customer_id: typeof s.customer === "string" ? s.customer : null,
      });
    }
    return res.status(200).json({ paid, app, plan });
  } catch (e) {
    console.error("pay/status:", e && e.message);
    return res.status(502).json({ error: "Session introuvable" });
  }
}
