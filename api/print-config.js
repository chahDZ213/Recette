// api/print-config.js — Barème Empreinte (tarifs) partagé.
//   GET  : lecture publique (l'app acheteur récupère les prix à afficher).
//   POST : écriture réservée au créateur (protégée par EMPREINTE_ADMIN_TOKEN).
// Le prix facturé est de toute façon recalculé côté serveur (api/pay/print-order.js)
// à partir de ce même barème → non contournable.
import { cors } from "./pay/_lib.js";
import { DEFAULT_CONFIG, readConfig, writeConfig, sanitize } from "./pay/_config.js";

export default async function handler(req, res) {
  if (cors(req, res)) return;

  if (req.method === "GET") {
    const cfg = await readConfig();
    return res.status(200).json({ config: cfg || DEFAULT_CONFIG, source: cfg ? "saved" : "default" });
  }

  if (req.method === "POST") {
    const expected = process.env.EMPREINTE_ADMIN_TOKEN || "";
    if (!expected) return res.status(500).json({ error: "Espace créateur non configuré (EMPREINTE_ADMIN_TOKEN manquant)" });
    const token = req.headers["x-admin-token"] || "";
    if (token !== expected) return res.status(401).json({ error: "Accès refusé" });
    if (!process.env.SUPABASE_SERVICE_ROLE_KEY) return res.status(500).json({ error: "Stockage non configuré (SUPABASE_SERVICE_ROLE_KEY manquante)" });

    const cfg = sanitize(req.body || {});
    const ok = await writeConfig(cfg);
    if (!ok) return res.status(502).json({ error: "Enregistrement du barème impossible" });
    return res.status(200).json({ config: cfg, saved: true });
  }

  return res.status(405).json({ error: "Méthode non autorisée" });
}
