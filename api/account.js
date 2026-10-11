// api/account.js — Droits RGPD sur le compte : suppression définitive.
// POST { action: "delete" } avec le jeton Supabase dans Authorization.
//
// La suppression efface, dans l'ordre : les photos générées de la personne
// dans Supabase Storage, ses lignes dans shares / recipes / premium_users,
// puis le compte d'authentification lui-même. Tout passe par la clé
// service_role côté serveur — jamais depuis le navigateur.
//
// Variables d'environnement : SUPABASE_SERVICE_ROLE_KEY (obligatoire),
// SUPABASE_URL et SUPABASE_ANON_KEY (valeurs par défaut du projet).

export const maxDuration = 30;

const SB_URL = process.env.SUPABASE_URL || "https://hpejfttwocclmqdtdiok.supabase.co";
const SB_ANON = process.env.SUPABASE_ANON_KEY || "sb_publishable_vXQvAJWpR0kKwQ-Fo9aWLw__0x3B7k5";
const BUCKET = "recipe-images";

function svc() { return process.env.SUPABASE_SERVICE_ROLE_KEY || ""; }
function svcHeaders(extra) {
  const k = svc();
  return Object.assign({ apikey: k, authorization: "Bearer " + k }, extra || {});
}

async function supabaseUserId(req) {
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

// Supprime les photos générées de la personne (préfixe gen/<uid>/).
async function deleteStoredPhotos(userId) {
  try {
    const list = await fetch(`${SB_URL}/storage/v1/object/list/${BUCKET}`, {
      method: "POST",
      headers: svcHeaders({ "content-type": "application/json" }),
      body: JSON.stringify({ prefix: `gen/${userId}`, limit: 1000 }),
    });
    if (!list.ok) return;
    const files = await list.json();
    const names = (Array.isArray(files) ? files : [])
      .map((f) => f && f.name)
      .filter(Boolean)
      .map((n) => `gen/${userId}/${n}`);
    if (!names.length) return;
    await fetch(`${SB_URL}/storage/v1/object/${BUCKET}`, {
      method: "DELETE",
      headers: svcHeaders({ "content-type": "application/json" }),
      body: JSON.stringify({ prefixes: names }),
    });
  } catch (e) {
    console.error("account/photos:", e && e.message);
  }
}

async function deleteRows(table, userId) {
  try {
    const r = await fetch(`${SB_URL}/rest/v1/${table}?user_id=eq.${encodeURIComponent(userId)}`, {
      method: "DELETE",
      headers: svcHeaders({ prefer: "return=minimal" }),
    });
    if (!r.ok) console.error("account/" + table + ":", r.status, (await r.text()).slice(0, 200));
    return r.ok;
  } catch (e) {
    console.error("account/" + table + ":", e && e.message);
    return false;
  }
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });

  const allowed = (process.env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (allowed.length) {
    const src = req.headers.origin || req.headers.referer || "";
    if (src && !allowed.some((a) => src.startsWith(a))) {
      return res.status(403).json({ error: "Origine non autorisée" });
    }
  }

  if (!svc()) {
    console.error("account: SUPABASE_SERVICE_ROLE_KEY manquante");
    return res.status(501).json({ error: "Suppression non configurée sur ce serveur." });
  }

  const userId = await supabaseUserId(req);
  if (!userId) return res.status(401).json({ error: "Connexion requise" });

  const action = (req.body && req.body.action) || "";
  if (action !== "delete") return res.status(400).json({ error: "Action inconnue" });

  try {
    await deleteStoredPhotos(userId);
    await deleteRows("shares", userId);
    await deleteRows("recipes", userId);
    await deleteRows("premium_users", userId);

    const del = await fetch(`${SB_URL}/auth/v1/admin/users/${encodeURIComponent(userId)}`, {
      method: "DELETE",
      headers: svcHeaders(),
    });
    if (!del.ok) {
      console.error("account/auth:", del.status, (await del.text()).slice(0, 300));
      return res.status(502).json({ error: "Les données ont été effacées, mais le compte n'a pas pu être supprimé. Réessaie." });
    }
    return res.status(200).json({ deleted: true });
  } catch (e) {
    console.error("account/delete:", e && e.message);
    return res.status(502).json({ error: "Suppression impossible pour le moment. Réessaie." });
  }
}
