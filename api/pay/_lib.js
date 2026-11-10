// api/pay/_lib.js — Utilitaires partagés des endpoints de paiement Stripe.
// Le backend de paiement est mutualisé : il sert mise. (ce projet), Kcalcul, Créno,
// ExaGe et quelques apps encore en démo, via un catalogue de produits par app.
// Aucune clé n'est committée : tout passe par les variables d'environnement Vercel.
//   STRIPE_SECRET_KEY            clé secrète — sk_test_… en test, sk_live_… en production
//   STRIPE_WEBHOOK_SECRET        secret du webhook (whsec_…) — un par mode, voir webhook.js
//   SUPABASE_SERVICE_ROLE_KEY    clé service_role — nécessaire pour activer le premium mise. côté serveur
//   PUBLIC_BASE_URL              URL publique de mise. (déjà utilisée par les push)
//
// TEST ou LIVE : c'est le préfixe de STRIPE_SECRET_KEY qui décide, rien d'autre.
// En live, les produits facturés sont ceux du catalogue Stripe du compte montappli
// (champ `price` ci-dessous) : le prix, la devise et le libellé viennent de Stripe,
// pas du code. En test, ces price IDs n'existent pas, donc on retombe sur les prix
// inline (`amount`/`currency`) pour pouvoir continuer à tester avec 4242…

import Stripe from "stripe";

// Mode déduit de la clé. Une clé absente ou restreinte (rk_…) est traitée comme test.
export const LIVE_MODE = /^sk_live_/.test(process.env.STRIPE_SECRET_KEY || "");

export const SB_URL = process.env.SUPABASE_URL || "https://hpejfttwocclmqdtdiok.supabase.co";
// clé publishable (déjà publique dans le front) — sert uniquement d'apikey pour valider les JWT
export const SB_ANON = process.env.SUPABASE_ANON_KEY || "sb_publishable_vXQvAJWpR0kKwQ-Fo9aWLw__0x3B7k5";

// ---- Catalogue produits ----
// `price`  : ID du prix LIVE dans le catalogue Stripe de montappli. Utilisé dès que la
//            clé est une sk_live_ — c'est Stripe qui fait foi pour le montant et la devise.
// `amount` / `currency` : prix inline de repli, utilisés en mode test uniquement.
//            Montants en centimes. `interval`/`intervalCount` seulement en mode "subscription".
// Une entrée sans `price` n'est pas encore au catalogue Stripe : elle reste en prix
// inline même en live (c'est volontaire, ce sont des apps pas encore commercialisées).
export const CATALOG = {
  mise: {
    // mise. Plus — prod_VV95exRdKwx9RA
    premium_month: {
      mode: "subscription", price: "price_1UU8nE3632fblzxLeO8LkUQp",
      currency: "gbp", amount: 299, interval: "month",
      name: "mise. Plus — mensuel",
      description: "Idées recettes, menu de la semaine, photo du frigo, création IA.",
      requiresAuth: true, // JWT Supabase obligatoire : le premium est rattaché au compte
    },
    premium_year: {
      mode: "subscription", price: "price_1UU9863632fblzxLCHLuDZXh",
      currency: "gbp", amount: 2499, interval: "year",
      name: "mise. Plus — annuel",
      description: "Le mensuel, avec deux mois offerts.",
      requiresAuth: true,
    },
  },
  kcalcul: {
    // Kcalcul Premium — prod_VV9KK4LNQWDwq2
    premium_month: {
      mode: "subscription", price: "price_1UU91n3632fblzxLrqcqjuuE",
      currency: "gbp", amount: 299, interval: "month",
      name: "Kcalcul Premium — mensuel",
      description: "Analyse photo illimitée, code-barres, historique complet et coach IA.",
    },
    premium_year: {
      mode: "subscription", price: "price_1UU91t3632fblzxLSBV4LVn1",
      currency: "gbp", amount: 2499, interval: "year",
      name: "Kcalcul Premium — annuel",
      description: "Le mensuel, avec deux mois offerts.",
    },
  },
  creno: {
    // Créno — prod_VV9LT1pb8nUAvM / prod_VV9L8uoU5zjYOt
    setup: {
      mode: "payment", price: "price_1UU92T3632fblzxLwJahXI4t",
      currency: "gbp", amount: 25000,
      name: "Créno — mise en service",
      description: "Paramétrage de l'agenda, comptes de l'équipe et prise en main.",
    },
    abo_month: {
      mode: "subscription", price: "price_1UU92N3632fblzxL4v7Ubuzc",
      currency: "gbp", amount: 4900, interval: "month",
      name: "Créno — abonnement mensuel",
      description: "Prise de rendez-vous en ligne pour le garage. Sans engagement.",
    },
  },
  metria: {
    // Pas encore au catalogue Stripe : prix inline, même en live.
    pro_month:   { mode: "subscription", currency: "eur", amount: 499,  interval: "month", name: "Metria Pro — mensuel" },
    pro_quarter: { mode: "subscription", currency: "eur", amount: 1199, interval: "month", intervalCount: 3, name: "Metria Pro — trimestriel" },
    pro_year:    { mode: "subscription", currency: "eur", amount: 3999, interval: "year",  name: "Metria Pro — annuel" },
  },
  echeance: {
    // Pas de compte dans échéance. (données locales au téléphone) : requiresAuth reste
    // false, et le statut payé est vérifié au retour via pay/status.js.
    bouclier_month: {
      mode: "subscription", currency: "eur", amount: 299, interval: "month",
      name: "échéance. — le Bouclier",
      description: "Alerte de découvert, scan des abonnements et simulateur d'économies.",
    },
    bouclier_year: {
      mode: "subscription", currency: "eur", amount: 2490, interval: "year",
      name: "échéance. — le Bouclier (annuel)",
      description: "Deux mois offerts par rapport au mensuel.",
    },
  },
  ltvtc: {
    // ExaGe — prod_VV9Ks1Fo9c7j0B. Achat unique ouvrant un accès à durée fixe.
    // `accessMonths` est la durée vendue : c'est elle qui sert à calculer la date
    // de fin d'accès côté app. Elle est recopiée dans les métadonnées de la session.
    access_3m:  { mode: "payment", price: "price_1UU9233632fblzxLvzr4vii3", currency: "chf", amount: 14900, accessMonths: 3,  name: "ExaGe — 3 mois d'accès" },
    access_6m:  { mode: "payment", price: "price_1UU9283632fblzxLEcyk4Gx9", currency: "chf", amount: 23900, accessMonths: 6,  name: "ExaGe — 6 mois d'accès" },
    access_9m:  { mode: "payment", price: "price_1UU92D3632fblzxLinOqA9vP", currency: "chf", amount: 29900, accessMonths: 9,  name: "ExaGe — 9 mois d'accès" },
    access_12m: { mode: "payment", price: "price_1UU92I3632fblzxLB3h6DkLo", currency: "chf", amount: 35000, accessMonths: 12, name: "ExaGe — 12 mois d'accès" },
    // Ancien bouton de démo, conservé le temps que l'app bascule sur les paliers
    // ci-dessus (sinon un client qui clique tombe sur « Produit inconnu »).
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
