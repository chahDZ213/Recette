// api/pay/status.js — Vérifie l'état d'une session Checkout (GET ?session_id=cs_test_…).
// Renvoie { paid, app, plan }. Si la session est payée et concerne mise., active aussi
// le premium côté serveur (filet de sécurité si le webhook n'est pas encore configuré —
// l'activation est idempotente : le webhook et ce endpoint écrivent la même ligne).
import { cors, getStripe, setMisePremium } from "./_lib.js";

export default async function handler(req, res) {
  if (cors(req, res)) return;
  if (req.method !== "GET") return res.status(405).json({ error: "Méthode non autorisée" });

  const stripe = getStripe();
  if (!stripe) return res.status(500).json({ error: "Paiement non configuré (STRIPE_SECRET_KEY manquante)" });

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
