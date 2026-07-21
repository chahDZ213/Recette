// api/pay/print-orders.js — Liste les commandes d'impression PAYÉES pour le dashboard
// créateur. Lit les sessions Stripe Checkout (mode test), garde celles marquées
// kind=print_order et payées, et renvoie l'essentiel : acheteur, adresse de livraison,
// détails de fabrication (métadonnées) et montant. Protégé par un token créateur.
//
// Env : STRIPE_SECRET_KEY, EMPREINTE_ADMIN_TOKEN (secret que tu choisis).
import { cors, getStripe } from "./_lib.js";

export default async function handler(req, res) {
  if (cors(req, res)) return;
  if (req.method !== "GET") return res.status(405).json({ error: "Méthode non autorisée" });

  const expected = process.env.EMPREINTE_ADMIN_TOKEN || "";
  if (!expected) return res.status(500).json({ error: "Dashboard non configuré (EMPREINTE_ADMIN_TOKEN manquant)" });
  const token = req.headers["x-admin-token"] || (req.query && req.query.token) || "";
  if (token !== expected) return res.status(401).json({ error: "Accès refusé" });

  const stripe = getStripe();
  if (!stripe) return res.status(500).json({ error: "Stripe non configuré (STRIPE_SECRET_KEY manquante)" });

  try {
    const list = await stripe.checkout.sessions.list({ limit: 100 });
    const orders = list.data
      .filter(s => s.metadata && s.metadata.kind === "print_order" && s.payment_status === "paid")
      .map(s => {
        const ship = s.shipping_details || (s.collected_information && s.collected_information.shipping_details) || null;
        const cust = s.customer_details || {};
        return {
          id: s.id,
          created: s.created,
          amountTotal: s.amount_total,
          amountShipping: (s.shipping_cost && s.shipping_cost.amount_total) || 0,
          currency: s.currency,
          email: cust.email || "",
          phone: cust.phone || "",
          name: (ship && ship.name) || cust.name || "",
          address: ship && ship.address ? ship.address : (cust.address || null),
          metadata: s.metadata || {},
        };
      })
      .sort((a, b) => b.created - a.created);
    return res.status(200).json({ orders });
  } catch (e) {
    console.error("pay/print-orders:", e && e.message);
    return res.status(502).json({ error: "Lecture des commandes impossible : " + ((e && e.message) || "erreur").slice(0, 200) });
  }
}
