// api/pay/print-order.js — Crée une session Stripe Checkout (MODE TEST) pour une
// commande d'impression 3D « Empreinte ». Contrairement à checkout.js (catalogue à
// prix fixes), le montant est DYNAMIQUE : c'est le prix de la pièce calculé côté client
// (matière + temps + marge). Stripe collecte l'adresse de livraison et applique les
// frais de port (gratuits au-dessus d'un seuil). Les détails de fabrication (filament,
// paramètres, grammes, minutes, lien du fichier STL) sont stockés dans les métadonnées
// de la session : le dashboard créateur les relit pour générer le bon de commande.
//
// Carte de test : 4242 4242 4242 4242, date future, CVC quelconque.
import { cors, getStripe, safeReturnUrl, withParams } from "./_lib.js";

// Pays de livraison autorisés (ajustable). Codes ISO à 2 lettres.
const SHIP_COUNTRIES = ["FR", "BE", "CH", "LU", "MC", "DE", "ES", "IT", "NL", "PT", "AT", "IE"];

// Bornes de sécurité sur le montant (centimes) : le prix vient du client, on évite
// les valeurs aberrantes. La revérification exacte demanderait de slicer côté serveur.
const MIN_CENTS = 100;        // 1,00 €
const MAX_CENTS = 2000000;    // 20 000 €

function clampCents(v) {
  const n = Math.round(Number(v));
  if (!Number.isFinite(n)) return null;
  return Math.max(MIN_CENTS, Math.min(MAX_CENTS, n));
}

// Barème créateur — doit rester aligné avec le catalogue de print/index.html.
// Le prix est recalculé ici pour ne pas dépendre du montant envoyé par le client.
const SERVER_TARIFS = {
  pla:  { pricePerG: 0.030, pricePerMin: 0.020 },
  petg: { pricePerG: 0.035, pricePerMin: 0.022 },
  asa:  { pricePerG: 0.045, pricePerMin: 0.024 },
  abs:  { pricePerG: 0.030, pricePerMin: 0.024 },
  tpu:  { pricePerG: 0.060, pricePerMin: 0.040 },
  pa:   { pricePerG: 0.070, pricePerMin: 0.030 },
};
const SERVER_MARGIN = 2.5; // € — préparation & marge

function recomputeAmount(order) {
  const t = SERVER_TARIFS[order && order.filamentId];
  const g = Number(order && order.grams), m = Number(order && order.minutes);
  if (!t || !Number.isFinite(g) || !Number.isFinite(m) || g <= 0 || m <= 0) return null;
  const euros = g * t.pricePerG + m * t.pricePerMin + SERVER_MARGIN;
  return clampCents(euros * 100);
}

// N'garde que des chaînes courtes pour les métadonnées Stripe (max 500 car/clé).
function meta(v, max = 480) {
  if (v == null) return "";
  return String(v).slice(0, max);
}

export default async function handler(req, res) {
  if (cors(req, res)) return;
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });

  const stripe = getStripe();
  if (!stripe) return res.status(500).json({ error: "Paiement non configuré (STRIPE_SECRET_KEY manquante)" });

  const body = req.body || {};
  const currency = (typeof body.currency === "string" && body.currency.length === 3) ? body.currency.toLowerCase() : "eur";
  const order = (body.order && typeof body.order === "object") ? body.order : {};

  // Prix facturé recalculé côté serveur à partir du barème créateur + des grammes/minutes
  // de la pièce ; on ne fait pas confiance au montant envoyé par le client. Si le filament
  // est inconnu, repli borné sur le montant client.
  const serverAmount = recomputeAmount(order);
  const amount = serverAmount != null ? serverAmount : clampCents(body.amount);
  if (amount == null) return res.status(400).json({ error: "Montant invalide" });

  // Frais de port : gratuits si la pièce atteint le seuil, sinon forfait.
  const shipFeeCents = clampCentsShip(body.shipFeeCents);        // forfait (centimes)
  const freeThresholdCents = clampCentsShip(body.freeThresholdCents); // seuil (centimes)
  const shippingFree = freeThresholdCents != null && amount >= freeThresholdCents;
  const shipCents = shippingFree ? 0 : (shipFeeCents || 0);

  const fallback = (process.env.PUBLIC_BASE_URL || "https://recette-xi.vercel.app").replace(/\/$/, "") + "/print/";
  const returnUrl = safeReturnUrl(body.returnUrl, fallback);

  // Métadonnées de fabrication (relues par le dashboard créateur pour le bon de commande).
  const metadata = {
    app: "empreinte",
    kind: "print_order",
    fileName: meta(order.fileName),
    fileUrl: meta(order.fileUrl),
    filament: meta(order.filament),
    filamentId: meta(order.filamentId),
    grams: meta(order.grams),
    minutes: meta(order.minutes),
    infill: meta(order.infill),
    dims: meta(order.dims),
    nozzle: meta(order.nozzle),
    bed: meta(order.bed),
    walls: meta(order.walls),
    exact: meta(order.exact),
    priceBreakdown: meta(order.priceBreakdown), // ex. "matière 0,18 € · temps 0,53 € · marge 2,50 €"
  };

  const pieceName = order.fileName ? `Impression 3D — ${meta(order.fileName, 120)}` : "Impression 3D à la demande";
  const pieceDesc = [order.filament && `Filament ${order.filament}`, order.grams && `${Math.round(order.grams)} g`,
                     order.minutes && `${Math.round(order.minutes)} min`].filter(Boolean).join(" · ").slice(0, 180);

  const shippingOption = {
    shipping_rate_data: {
      type: "fixed_amount",
      fixed_amount: { amount: shipCents, currency },
      display_name: shipCents === 0 ? "Livraison offerte" : "Livraison",
      delivery_estimate: {
        minimum: { unit: "business_day", value: 3 },
        maximum: { unit: "business_day", value: 7 },
      },
    },
  };

  try {
    const session = await stripe.checkout.sessions.create({
      mode: "payment",
      line_items: [{
        price_data: {
          currency,
          unit_amount: amount,
          product_data: { name: pieceName, ...(pieceDesc ? { description: pieceDesc } : {}) },
        },
        quantity: 1,
      }],
      shipping_address_collection: { allowed_countries: SHIP_COUNTRIES },
      shipping_options: [shippingOption],
      phone_number_collection: { enabled: true },
      success_url: withParams(returnUrl, "pay=success&session_id={CHECKOUT_SESSION_ID}"),
      cancel_url: withParams(returnUrl, "pay=cancel"),
      metadata,
      payment_intent_data: { metadata },  // recopie sur le paiement (utile pour le dashboard)
    });
    return res.status(200).json({ url: session.url, sessionId: session.id, shippingFree, shipCents });
  } catch (e) {
    console.error("pay/print-order:", e && e.message);
    return res.status(502).json({ error: "Création de la session Stripe impossible : " + ((e && e.message) || "erreur inconnue").slice(0, 200) });
  }
}

function clampCentsShip(v) {
  if (v == null) return null;
  const n = Math.round(Number(v));
  if (!Number.isFinite(n) || n < 0) return null;
  return Math.min(n, 100000); // max 1000 € de port, garde-fou
}
