// api/pay/_config.js — Barème éditable d'Empreinte (tarifs filaments, suppléments
// couleur, marge, livraison), stocké dans Supabase Storage sous forme d'un simple JSON.
// Le bucket se crée tout seul au premier enregistrement (aucune manip Supabase requise).
// Lu par l'app acheteur (affichage) ET par api/pay/print-order.js (prix facturé recalculé).
import { SB_URL } from "./_lib.js";

const BUCKET = "print-config";
const OBJECT = "config.json";

// Valeurs par défaut — doivent rester alignées avec le catalogue de print/index.html.
export const DEFAULT_CONFIG = {
  filaments: {
    pla:  { pricePerG: 0.030, pricePerMin: 0.020 },
    petg: { pricePerG: 0.035, pricePerMin: 0.022 },
    asa:  { pricePerG: 0.045, pricePerMin: 0.024 },
    abs:  { pricePerG: 0.030, pricePerMin: 0.024 },
    tpu:  { pricePerG: 0.060, pricePerMin: 0.040 },
    pa:   { pricePerG: 0.070, pricePerMin: 0.030 },
  },
  colors: {
    black:0, white:0, grey:0,
    red:1.5, orange:1.5, yellow:1.5, green:1.5, blue:1.5, purple:1.5, pink:1.5,
    gold:3, silver:3, transparent:3, glow:4,
  },
  margin: 2.5,     // € — préparation & marge
  freeShip: 40,    // € — livraison gratuite au-dessus de ce montant
  shipFee: 4.9,    // € — forfait livraison sinon
};

function svcKey() { return process.env.SUPABASE_SERVICE_ROLE_KEY || ""; }

// Lit le barème enregistré (ou null si absent / non configuré).
export async function readConfig() {
  const svc = svcKey();
  if (!svc) return null;
  try {
    const r = await fetch(`${SB_URL}/storage/v1/object/${BUCKET}/${OBJECT}`, {
      headers: { apikey: svc, authorization: "Bearer " + svc },
    });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

async function ensureBucket(svc) {
  // idempotent : crée le bucket privé s'il n'existe pas encore
  await fetch(`${SB_URL}/storage/v1/bucket`, {
    method: "POST",
    headers: { apikey: svc, authorization: "Bearer " + svc, "content-type": "application/json" },
    body: JSON.stringify({ id: BUCKET, name: BUCKET, public: false }),
  }).catch(() => {});
}

// Enregistre le barème (upsert). Renvoie true si OK.
export async function writeConfig(config) {
  const svc = svcKey();
  if (!svc) return false;
  await ensureBucket(svc);
  try {
    const r = await fetch(`${SB_URL}/storage/v1/object/${BUCKET}/${OBJECT}`, {
      method: "POST",
      headers: {
        apikey: svc, authorization: "Bearer " + svc,
        "content-type": "application/json", "x-upsert": "true",
      },
      body: JSON.stringify(config),
    });
    return r.ok;
  } catch { return false; }
}

// N'accepte que des nombres >= 0, sur les clés connues (le reste = valeurs par défaut).
export function sanitize(input) {
  const cfg = JSON.parse(JSON.stringify(DEFAULT_CONFIG));
  const num = (v, d) => { const n = Number(v); return Number.isFinite(n) && n >= 0 ? n : d; };
  if (input && input.filaments) {
    for (const id in cfg.filaments) {
      const f = input.filaments[id];
      if (f) {
        cfg.filaments[id].pricePerG = num(f.pricePerG, cfg.filaments[id].pricePerG);
        cfg.filaments[id].pricePerMin = num(f.pricePerMin, cfg.filaments[id].pricePerMin);
      }
    }
  }
  if (input && input.colors) {
    for (const id in cfg.colors) cfg.colors[id] = num(input.colors[id], cfg.colors[id]);
  }
  if (input) {
    cfg.margin = num(input.margin, cfg.margin);
    cfg.freeShip = num(input.freeShip, cfg.freeShip);
    cfg.shipFee = num(input.shipFee, cfg.shipFee);
  }
  return cfg;
}
