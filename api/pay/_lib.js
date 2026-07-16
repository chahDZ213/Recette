// api/pay/_lib.js — Utilitaires partagés des endpoints de paiement Stripe (MODE TEST / démo).
// Le backend de paiement est mutualisé : il sert mise. (ce projet), Metria (app Expo)
// et LTVTC Topo (PWA statique), via un catalogue de produits par app.
// Aucune clé n'est committée : tout passe par les variables d'environnement Vercel.
//   STRIPE_SECRET_KEY            clé secrète TEST (sk_test_…) — obligatoire
//   STRIPE_WEBHOOK_SECRET        secret du webhook (whsec_…) — optionnel (voir webhook.js)
//   SUPABASE_SERVICE_ROLE_KEY    clé service_role — nécessaire pour activer le premium mise. côté serveur
//   PUBLIC_BASE_URL              URL publique de mise. (déjà utilisée par les push)

import Stripe from "stripe";

export const SB_URL = process.env.SUPABASE_URL || "https://hpejfttwocclmqdtdiok.supabase.co";
// clé publishable (déjà publique dans le front) — sert uniquement d'apikey pour valider les JWT
export const SB_ANON = process.env.SUPABASE_ANON_KEY || "sb_publishable_vXQvAJWpR0kKwQ-Fo9aWLw__0x3B7k5";

// ---- Catalogue produits (prix inline via price_data : rien à créer dans le dashboard Stripe) ----
// Montants en centimes. `interval`/`intervalCount` uniquement pour mode "subscription".
export const CATALOG = {
  mise: {
    premium_month: {
      mode: "subscription", currency: "eur", amount: 399, interval: "month",
      name: "mise. premium — mensuel",
      description: "Idées recettes, menu de la semaine, photo du frigo, création IA.",
      requiresAuth: true, // JWT Supabase obligatoire : le premium est rattaché au compte
    },
  },
  metria: {
    pro_month:   { mode: "subscription", currency: "eur", amount: 499,  interval: "month", name: "Metria Pro — mensuel" },
    pro_quarter: { mode: "subscription", currency: "eur", amount: 1199, interval: "month", intervalCount: 3, name: "Metria Pro — trimestriel" },
    pro_year:    { mode: "subscription", currency: "eur", amount: 3999, interval: "year",  name: "Metria Pro — annuel" },
  },
  ltvtc: {
    soutien: {
      mode: "payment", currency: "chf", amount: 990,
      name: "LTVTC Topo — soutien",
      description: "Paiement unique de soutien (démo). Merci !",
    },
  },
};

let _stripe = null;
export function getStripe() {
  const key = process.env.STRIPE_SECRET_KEY || "";
  if (!key) return null;
  if (!_stripe) _stripe = new Stripe(key);
  return _stripe;
}

// CORS ouvert : les 3 apps (origines différentes, dont localhost) appellent ces endpoints.
// Pas de cookies — l'auth mise. passe par le header Authorization, compatible avec "*".
export function cors(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
  if (req.method === "OPTIONS") { res.status(204).end(); return true; }
  return false;
}

// Valide un JWT Supabase et renvoie l'id utilisateur (même logique que api/generate-image.js).
export async function supabaseUserId(req) {
  const jwt = (req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (!jwt) return null;
  try {
    const u = await fetch(SB_URL + "/auth/v1/user", {
      headers: { apikey: SB_ANON, authorization: "Bearer " + jwt },
    });
    if (!u.ok) return null;
    return (await u.json()).id || null;
  } catch { return null; }
}

// Active (ou désactive) le premium mise. d'un utilisateur — écrit dans public.premium_users
// avec la clé service_role (la table n'a aucune policy d'écriture : seul le serveur écrit).
export async function setMisePremium(userId, fields) {
  const svc = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  if (!svc) { console.warn("pay: SUPABASE_SERVICE_ROLE_KEY manquante — premium non enregistré côté serveur"); return false; }
  const r = await fetch(SB_URL + "/rest/v1/premium_users?on_conflict=user_id", {
    method: "POST",
    headers: {
      apikey: svc, authorization: "Bearer " + svc,
      "content-type": "application/json",
      prefer: "resolution=merge-duplicates",
    },
    body: JSON.stringify({ user_id: userId, updated_at: new Date().toISOString(), ...fields }),
  });
  if (!r.ok) console.warn("pay: upsert premium_users a échoué", r.status, (await r.text()).slice(0, 300));
  return r.ok;
}

// URL de retour fournie par le client (l'app qui ouvre le Checkout). On la borne
// à http(s) et à une longueur raisonnable pour éviter les redirections farfelues.
export function safeReturnUrl(u, fallback) {
  if (typeof u !== "string" || u.length > 500) return fallback;
  if (!/^https?:\/\//i.test(u)) return fallback;
  return u.split("#")[0];
}

export function withParams(base, extra) {
  return base + (base.includes("?") ? "&" : "?") + extra;
}
