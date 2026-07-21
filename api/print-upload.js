// api/print-upload.js — Reçoit le fichier STL d'une commande Empreinte et le dépose
// dans le stockage Supabase (bucket `print-files`) avec la clé service_role. Renvoie
// une URL de téléchargement que le bon de commande (dashboard créateur) réutilise.
//
// Prérequis (une seule fois, quand tu donnes le feu vert) :
//   - créer un bucket Supabase Storage nommé `print-files` (public).
// Tant que le bucket n'existe pas, l'upload échoue proprement et la commande part
// sans fichier auto-attaché (le front gère ce cas).
//
// Env : SUPABASE_URL (ou défaut mise.), SUPABASE_SERVICE_ROLE_KEY.
import { SB_URL, cors } from "./pay/_lib.js";

export const config = { api: { bodyParser: false } }; // on lit le flux binaire nous-mêmes

const BUCKET = "print-files";
const MAX_BYTES = 4_400_000; // ~4,4 Mo — marge sous la limite serverless de Vercel

function safeName(n) {
  return String(n || "piece.stl").replace(/[^\w.\-]+/g, "_").slice(0, 80) || "piece.stl";
}

async function readBody(req) {
  const chunks = [];
  let total = 0;
  for await (const c of req) {
    total += c.length;
    if (total > MAX_BYTES) throw new Error("too_large");
    chunks.push(c);
  }
  return Buffer.concat(chunks);
}

export default async function handler(req, res) {
  if (cors(req, res)) return;
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });

  const svc = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  if (!svc) return res.status(500).json({ error: "Stockage non configuré (SUPABASE_SERVICE_ROLE_KEY manquante)" });

  let buf;
  try {
    buf = await readBody(req);
  } catch (e) {
    if (e && e.message === "too_large") return res.status(413).json({ error: "Fichier trop volumineux (max ~4,4 Mo)" });
    return res.status(400).json({ error: "Lecture du fichier impossible" });
  }
  if (!buf || !buf.length) return res.status(400).json({ error: "Fichier vide" });

  const name = safeName(req.headers["x-filename"]);
  const path = `orders/${Date.now()}-${Math.random().toString(36).slice(2, 8)}-${name}`;

  try {
    const up = await fetch(`${SB_URL}/storage/v1/object/${BUCKET}/${path}`, {
      method: "POST",
      headers: {
        apikey: svc,
        authorization: "Bearer " + svc,
        "content-type": "model/stl",
        "x-upsert": "false",
      },
      body: buf,
    });
    if (!up.ok) {
      const detail = (await up.text()).slice(0, 200);
      console.warn("print-upload: échec stockage", up.status, detail);
      return res.status(502).json({ error: "Stockage indisponible (bucket manquant ?)", detail });
    }
    const url = `${SB_URL}/storage/v1/object/public/${BUCKET}/${path}`;
    return res.status(200).json({ url, path, bytes: buf.length });
  } catch (e) {
    console.error("print-upload:", e && e.message);
    return res.status(502).json({ error: "Upload impossible" });
  }
}
