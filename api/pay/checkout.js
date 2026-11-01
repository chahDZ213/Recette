// api/pay/checkout.js — Crée une session Stripe Checkout pour l'une des apps
// du catalogue (mise. / Kcalcul / Créno / ExaGe…). Reçoit { app, plan, returnUrl } et renvoie
// { url, sessionId } : le client redirige l'utilisateur vers `url` (page Stripe hébergée).
// Test (sk_test_) : carte 4242 4242 4242 4242. Live (sk_live_) : prix du catalogue Stripe.
import { CATALOG, LIVE_MODE, cors, getStripe, safeReturnUrl, supabaseUserId, withParams } from "./_lib.js";

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

  /* Consentements obligatoires avant un abonnement à accès immédiat (UK
     Consumer Contracts Regulations 2013) : la personne demande à en profiter
     tout de suite ET renonce par là même à ses 14 jours de rétractation.
     Sans les deux, pas de session. Ils sont horodatés et rangés dans les
     métadonnées Stripe, qui les conserve et les rend exportables : c'est la
     preuve à produire en cas de contestation de paiement. */
  const c = body.consents || {};
  const consentRequired = product.mode === "subscription" || product.mode === "payment";
  if (consentRequired && !(c.immediateAccess === true && c.withdrawalWaiver === true)) {
    return res.status(400).json({ error: "Les deux cases doivent être cochées pour continuer." });
  }
  const consentAt = new Date().toISOString();

  const metadata = {
    app, plan,
    ...(userId ? { userId } : {}),
    ...(product.accessMonths ? { access_months: String(product.accessMonths) } : {}),
    ...(consentRequired ? {
      consent_immediate_access: "true",
      consent_withdrawal_waiver: "true",
      consent_at: consentAt,
    } : {}),
  };

  /* En live, on facture le prix du catalogue Stripe (price_…) : le montant, la
     devise et le libellé viennent de Stripe, donc un changement de tarif se fait
     dans le dashboard sans redéployer, et le portail client sait proposer les
     autres paliers du même produit. En test ces IDs n'existent pas, d'où le
     repli sur un prix inline. */
  const lineItem = LIVE_MODE && product.price
    ? { price: product.price, quantity: 1 }
    : {
        quantity: 1,
        price_data: {
          currency: product.currency,
          unit_amount: product.amount,
          product_data: { name: product.name, ...(product.description ? { description: product.description } : {}) },
          ...(product.mode === "subscription"
            ? { recurring: { interval: product.interval, interval_count: product.intervalCount || 1 } }
            : {}),
        },
      };

  try {
    const session = await stripe.checkout.sessions.create({
      mode: product.mode,
      line_items: [lineItem],
      success_url: withParams(returnUrl, "pay=success&session_id={CHECKOUT_SESSION_ID}"),
      cancel_url: withParams(returnUrl, "pay=cancel"),
      metadata,
      ...(userId ? { client_reference_id: userId } : {}),
      // Recopie les métadonnées sur l'abonnement : permet au webhook de retrouver
      // l'utilisateur lors d'une résiliation (customer.subscription.deleted).
      ...(product.mode === "subscription" ? { subscription_data: { metadata } } : {}),
    }, {
      /* Clé d'idempotence : un double-clic ou un renvoi réseau ne doit pas
         créer deux sessions de paiement. Même minute + même compte + même
         produit = Stripe renvoie la session déjà créée. */
      idempotencyKey: ["co", app, plan, userId || "anon", consentAt.slice(0, 16)].join(":"),
    });
    return res.status(200).json({ url: session.url, sessionId: session.id });
  } catch (e) {
    console.error("pay/checkout:", e && e.message);
    return res.status(502).json({ error: "Création de la session Stripe impossible : " + ((e && e.message) || "erreur inconnue").slice(0, 200) });
  }
}
