// api/pay/checkout.js — Crée une session Stripe Checkout (MODE TEST) pour l'une des apps
// du catalogue (mise. / Metria / LTVTC Topo). Reçoit { app, plan, returnUrl } et renvoie
// { url, sessionId } : le client redirige l'utilisateur vers `url` (page Stripe hébergée).
// Carte de test : 4242 4242 4242 4242, date future, CVC quelconque.
import { CATALOG, cors, getStripe, safeReturnUrl, supabaseUserId, withParams } from "./_lib.js";

export default async function handler(req, res) {
  if (cors(req, res)) return;
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });

  const stripe = getStripe();
  if (!stripe) return res.status(500).json({ error: "Paiement non configuré (STRIPE_SECRET_KEY manquante)" });

  const body = req.body || {};
  const app = typeof body.app === "string" ? body.app : "";
  const plan = typeof body.plan === "string" ? body.plan : "";
  const product = CATALOG[app] && CATALOG[app][plan];
  if (!product) return res.status(400).json({ error: "Produit inconnu (app/plan invalide)" });

  // mise. : le premium est rattaché au compte → connexion obligatoire.
  let userId = null;
  if (product.requiresAuth) {
    userId = await supabaseUserId(req);
    if (!userId) return res.status(401).json({ error: "Connexion requise" });
  }

  const fallback = (process.env.PUBLIC_BASE_URL || "https://recette-xi.vercel.app").replace(/\/$/, "") + "/";
  const returnUrl = safeReturnUrl(body.returnUrl, fallback);

  const metadata = { app, plan, ...(userId ? { userId } : {}) };
  const priceData = {
    currency: product.currency,
    unit_amount: product.amount,
    product_data: { name: product.name, ...(product.description ? { description: product.description } : {}) },
    ...(product.mode === "subscription"
      ? { recurring: { interval: product.interval, interval_count: product.intervalCount || 1 } }
      : {}),
  };

  try {
    const session = await stripe.checkout.sessions.create({
      mode: product.mode,
      line_items: [{ price_data: priceData, quantity: 1 }],
      success_url: withParams(returnUrl, "pay=success&session_id={CHECKOUT_SESSION_ID}"),
      cancel_url: withParams(returnUrl, "pay=cancel"),
      metadata,
      ...(userId ? { client_reference_id: userId } : {}),
      // Recopie les métadonnées sur l'abonnement : permet au webhook de retrouver
      // l'utilisateur lors d'une résiliation (customer.subscription.deleted).
      ...(product.mode === "subscription" ? { subscription_data: { metadata } } : {}),
    });
    return res.status(200).json({ url: session.url, sessionId: session.id });
  } catch (e) {
    console.error("pay/checkout:", e && e.message);
    return res.status(502).json({ error: "Création de la session Stripe impossible : " + ((e && e.message) || "erreur inconnue").slice(0, 200) });
  }
}
