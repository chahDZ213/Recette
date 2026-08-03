// api/print.js — Endpoint UNIQUE d'Empreinte, consolidé pour rester sous la limite de
// 12 fonctions serverless du plan Vercel Hobby. On route par ?action= :
//   GET  ?action=config  → barème public (l'app acheteur lit les prix)
//   POST ?action=config  → enregistre le barème (réservé au créateur, token)
//   GET  ?action=orders  → commandes payées (réservé au créateur, token)
//   POST ?action=order   → crée une session Stripe Checkout (commande client)
// (L'upload du fichier STL reste séparé — api/print-upload.js — car il lit un flux binaire.)
import { cors, getStripe, safeReturnUrl, withParams } from "./pay/_lib.js";
import { DEFAULT_CONFIG, readConfig, writeConfig, sanitize } from "./pay/_config.js";

const SHIP_COUNTRIES = ["FR", "BE", "CH", "LU", "MC", "DE", "ES", "IT", "NL", "PT", "AT", "IE"];
const MIN_CENTS = 100;       // 1,00 €
const MAX_CENTS = 2000000;   // 20 000 €

function clampCents(v) {
  const n = Math.round(Number(v));
  if (!Number.isFinite(n)) return null;
  return Math.max(MIN_CENTS, Math.min(MAX_CENTS, n));
}
function meta(v, max = 480) { return v == null ? "" : String(v).slice(0, max); }

// Prix recalculé à partir du barème créateur — pas de confiance au montant du client.
function recomputeAmount(order, cfg) {
  const t = cfg.filaments && cfg.filaments[order && order.filamentId];
  const g = Number(order && order.grams), m = Number(order && order.minutes);
  if (!t || !Number.isFinite(g) || !Number.isFinite(m) || g <= 0 || m <= 0) return null;
  const colorSurcharge = (cfg.colors && cfg.colors[order && order.colorId]) || 0;
  const euros = g * t.pricePerG + m * t.pricePerMin + (Number(cfg.margin) || 0) + colorSurcharge;
  return clampCents(euros * 100);
}

function adminGate(req) {
  const expected = process.env.EMPREINTE_ADMIN_TOKEN || "";
  if (!expected) return { code: 500, error: "Espace créateur non configuré (EMPREINTE_ADMIN_TOKEN manquant)" };
  const token = req.headers["x-admin-token"] || (req.query && req.query.token) || "";
  if (token !== expected) return { code: 401, error: "Accès refusé" };
  return null;
}

// ---------- action=config ----------
async function handleConfig(req, res) {
  if (req.method === "GET") {
    const cfg = await readConfig();
    return res.status(200).json({ config: cfg || DEFAULT_CONFIG, source: cfg ? "saved" : "default" });
  }
  if (req.method === "POST") {
    const gate = adminGate(req); if (gate) return res.status(gate.code).json({ error: gate.error });
    if (!process.env.SUPABASE_SERVICE_ROLE_KEY) return res.status(500).json({ error: "Stockage non configuré (SUPABASE_SERVICE_ROLE_KEY manquante)" });
    const cfg = sanitize(req.body || {});
    const ok = await writeConfig(cfg);
    if (!ok) return res.status(502).json({ error: "Enregistrement du barème impossible" });
    return res.status(200).json({ config: cfg, saved: true });
  }
  return res.status(405).json({ error: "Méthode non autorisée" });
}

// ---------- action=orders ----------
async function handleOrders(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "Méthode non autorisée" });
  const gate = adminGate(req); if (gate) return res.status(gate.code).json({ error: gate.error });
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
          id: s.id, created: s.created, amountTotal: s.amount_total,
          amountShipping: (s.shipping_cost && s.shipping_cost.amount_total) || 0,
          currency: s.currency, email: cust.email || "", phone: cust.phone || "",
          name: (ship && ship.name) || cust.name || "",
          address: ship && ship.address ? ship.address : (cust.address || null),
          metadata: s.metadata || {},
        };
      })
      .sort((a, b) => b.created - a.created);
    return res.status(200).json({ orders });
  } catch (e) {
    console.error("print/orders:", e && e.message);
    return res.status(502).json({ error: "Lecture des commandes impossible : " + ((e && e.message) || "erreur").slice(0, 200) });
  }
}

// ---------- action=order (création de la session Checkout) ----------
async function handleOrder(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });
  const stripe = getStripe();
  if (!stripe) return res.status(500).json({ error: "Paiement non configuré (STRIPE_SECRET_KEY manquante)" });

  const body = req.body || {};
  const currency = (typeof body.currency === "string" && body.currency.length === 3) ? body.currency.toLowerCase() : "eur";
  const order = (body.order && typeof body.order === "object") ? body.order : {};

  const cfg = (await readConfig()) || DEFAULT_CONFIG;
  const serverAmount = recomputeAmount(order, cfg);
  const amount = serverAmount != null ? serverAmount : clampCents(body.amount);
  if (amount == null) return res.status(400).json({ error: "Montant invalide" });

  const freeCents = Math.round((Number(cfg.freeShip) || 0) * 100);
  const feeCents = Math.round((Number(cfg.shipFee) || 0) * 100);
  const shippingFree = freeCents > 0 && amount >= freeCents;
  const shipCents = shippingFree ? 0 : feeCents;

  const fallback = (process.env.PUBLIC_BASE_URL || "https://recette-xi.vercel.app").replace(/\/$/, "") + "/print/";
  const returnUrl = safeReturnUrl(body.returnUrl, fallback);

  const metadata = {
    app: "empreinte", kind: "print_order",
    fileName: meta(order.fileName), fileUrl: meta(order.fileUrl),
    filament: meta(order.filament), filamentId: meta(order.filamentId), color: meta(order.color),
    grams: meta(order.grams), minutes: meta(order.minutes), infill: meta(order.infill),
    dims: meta(order.dims), nozzle: meta(order.nozzle), bed: meta(order.bed), walls: meta(order.walls),
    exact: meta(order.exact), priceBreakdown: meta(order.priceBreakdown),
  };

  const pieceName = order.fileName ? `Impression 3D — ${meta(order.fileName, 120)}` : "Impression 3D à la demande";
  const pieceDesc = [order.filament && `Filament ${order.filament}`, order.grams && `${Math.round(order.grams)} g`,
                     order.minutes && `${Math.round(order.minutes)} min`].filter(Boolean).join(" · ").slice(0, 180);

  const shippingOption = {
    shipping_rate_data: {
      type: "fixed_amount",
      fixed_amount: { amount: shipCents, currency },
      display_name: shipCents === 0 ? "Livraison offerte" : "Livraison",
      delivery_estimate: { minimum: { unit: "business_day", value: 3 }, maximum: { unit: "business_day", value: 7 } },
    },
  };

  try {
    const session = await stripe.checkout.sessions.create({
      mode: "payment",
      line_items: [{
        price_data: { currency, unit_amount: amount, product_data: { name: pieceName, ...(pieceDesc ? { description: pieceDesc } : {}) } },
        quantity: 1,
      }],
      shipping_address_collection: { allowed_countries: SHIP_COUNTRIES },
      shipping_options: [shippingOption],
      phone_number_collection: { enabled: true },
      success_url: withParams(returnUrl, "pay=success&session_id={CHECKOUT_SESSION_ID}"),
      cancel_url: withParams(returnUrl, "pay=cancel"),
      metadata,
      payment_intent_data: { metadata },
    });
    return res.status(200).json({ url: session.url, sessionId: session.id, shippingFree, shipCents });
  } catch (e) {
    console.error("print/order:", e && e.message);
    return res.status(502).json({ error: "Création de la session Stripe impossible : " + ((e && e.message) || "erreur inconnue").slice(0, 200) });
  }
}

export default async function handler(req, res) {
  if (cors(req, res)) return;
  const action = (req.query && req.query.action) || "";
  if (action === "config") return handleConfig(req, res);
  if (action === "orders") return handleOrders(req, res);
  if (action === "order")  return handleOrder(req, res);
  return res.status(400).json({ error: "Action inconnue (config | orders | order)" });
}
