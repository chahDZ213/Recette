// api/budget.js — endpoint unique de l'app échéance. (/budget/).
//
// ⚠️ Pourquoi un seul fichier pour quatre actions : le plan Vercel Hobby limite un
// déploiement à 12 fonctions serverless, et le dépôt en compte déjà 11. Séparer la
// planification et l'envoi ferait échouer tout le déploiement. Les fichiers préfixés
// par « _ » ne comptent pas comme des routes, d'où _budget-core.js / _budget-notify.js.
//
// Actions (dans le corps JSON) :
//   set    → crée/remplace la planification quotidienne QStash        (appelée par l'app)
//   clear  → supprime la planification                                (appelée par l'app)
//   test   → envoie tout de suite la notification du jour             (appelée par l'app)
//   push   → calcule le jour et envoie le push                        (appelée par QStash, exige SEND_SECRET)
export const maxDuration = 30;

import webpush from "web-push";
import { todayLocal } from "./_budget-core.js";
import { composeNotification } from "./_budget-notify.js";

const QSTASH_URL = process.env.QSTASH_URL;
const QSTASH_TOKEN = process.env.QSTASH_TOKEN;
const SEND_SECRET = process.env.SEND_SECRET;
const BASE_URL = process.env.PUBLIC_BASE_URL;

const VAPID_PUBLIC = process.env.VAPID_PUBLIC_KEY;
const VAPID_PRIVATE = process.env.VAPID_PRIVATE_KEY;
if (VAPID_PUBLIC && VAPID_PRIVATE) {
  webpush.setVapidDetails("mailto:contact@mise.app", VAPID_PUBLIC, VAPID_PRIVATE);
}

const MAX_ITEMS = 400;
const clampStr = (v, n) => (typeof v === "string" ? v.slice(0, n) : "");

// On ne garde que les champs utiles au calcul : la planification QStash reste légère
// et aucune donnée superflue ne sort du téléphone.
function sanitize(data = {}) {
  const items = Array.isArray(data.items) ? data.items.slice(0, MAX_ITEMS) : [];
  return {
    items: items.map((it) => ({
      id: clampStr(it.id, 40),
      label: clampStr(it.label, 60),
      amount: Number(it.amount) || 0,
      kind: ["debit", "manual", "income"].includes(it.kind) ? it.kind : "debit",
      freq: clampStr(it.freq, 12) || "monthly",
      day: Number(it.day) || 1,
      weekday: Number(it.weekday) || 0,
      anchorMonth: Number(it.anchorMonth) || 0,
      date: clampStr(it.date, 10),
      start: clampStr(it.start, 10),
      end: clampStr(it.end, 10),
      paused: !!it.paused,
      notifyDaysBefore: Math.max(0, Math.min(30, Number(it.notifyDaysBefore) || 0)),
    })),
    paid: (Array.isArray(data.paid) ? data.paid : []).slice(0, 400).map((k) => clampStr(k, 60)),
    currency: clampStr(data.currency, 4) || "EUR",
    locale: clampStr(data.locale, 10) || "fr-FR",
    shiftWeekend: !!data.shiftWeekend,
    aheadDays: Math.max(1, Math.min(31, Number(data.aheadDays) || 7)),
    quietIfEmpty: data.quietIfEmpty !== false,
    tzOffset: Math.max(-840, Math.min(840, Number(data.tzOffset) || 0)),
    // Bouclier découvert
    solde: Number.isFinite(Number(data.solde)) && data.solde !== null && data.solde !== "" ? Number(data.solde) : null,
    soldeDate: clampStr(data.soldeDate, 10),
    seuil: Number(data.seuil) || 0,
    alerteJours: Math.max(1, Math.min(14, Number(data.alerteJours) || 3)),
    premium: !!data.premium,
  };
}

async function qstash(path, init = {}) {
  return fetch(`${QSTASH_URL}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${QSTASH_TOKEN}`, ...(init.headers || {}) },
  });
}

async function supprimerPlanification(scheduleId) {
  if (!scheduleId) return;
  try { await qstash(`/v2/schedules/${encodeURIComponent(scheduleId)}`, { method: "DELETE" }); } catch {}
}

// ─── Lecture d'une capture d'écran par Claude Vision ───
// Cas d'usage principal : iOS → Réglages → [ton nom] → Abonnements, qui liste tous
// les abonnements App Store. Marche aussi sur un relevé bancaire photographié.
const CATEGORIES = "logement, energie, telecom, transport, assurance, credit, abo, impots, sante, courses, epargne, salaire, autre";

const PROMPT_SCAN = `Tu regardes une capture d'écran ou une photo fournie par un utilisateur francophone :
soit la liste de ses abonnements (écran « Abonnements » d'iOS/Android, page d'un compte),
soit un relevé bancaire, soit une liste écrite de dépenses récurrentes.

Extrais UNIQUEMENT les dépenses et revenus RÉCURRENTS que tu peux lire avec certitude.
Ignore les achats ponctuels du passé, les soldes, les totaux et les frais bancaires isolés.

Réponds STRICTEMENT par un objet JSON, sans texte autour :
{"items":[{"label":"Netflix","amount":13.49,"kind":"debit","freq":"monthly","day":5,"anchorMonth":0,"category":"abo","note":""}]}

Règles :
- "label" : le nom du marchand, court et propre (« Netflix », pas « NETFLIX.COM 4972 »).
- "amount" : nombre positif, en unités (13.49). Jamais de symbole monétaire.
- "kind" : "debit" si c'est prélevé automatiquement, "manual" si l'utilisateur doit payer
  lui-même (loyer versé par virement, facture à régler), "income" pour une entrée d'argent.
  Dans le doute sur un abonnement : "debit".
- "freq" : "monthly", "weekly", "quarterly", "semiannual", "yearly" ou "once".
  Un abonnement mensuel = "monthly", annuel = "yearly".
- "day" : jour du mois (1-31) si tu le vois ou peux le déduire d'une date de renouvellement,
  sinon 1. "anchorMonth" : mois (0=janvier) pour les fréquences annuelles/trimestrielles, sinon 0.
- "category" : une seule valeur parmi ${CATEGORIES}.
- Si tu ne lis rien d'exploitable, renvoie {"items":[]}.`;

async function scanImage(body, res) {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) return res.status(500).json({ error: "Scan non configuré (ANTHROPIC_API_KEY manquante)" });

  const m = /^data:(image\/[a-zA-Z0-9.+-]+);base64,([\s\S]+)$/.exec(body.image || "");
  if (!m) return res.status(400).json({ error: "Image invalide" });
  if (m[2].length > 5_000_000) return res.status(413).json({ error: "Image trop lourde (réduis la qualité)" });

  try {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01" },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 1800,
        messages: [{
          role: "user",
          content: [
            { type: "image", source: { type: "base64", media_type: m[1], data: m[2] } },
            { type: "text", text: PROMPT_SCAN },
          ],
        }],
      }),
    });
    const data = await r.json();
    if (!r.ok) return res.status(502).json({ error: "Lecture impossible", detail: (data.error && data.error.message) || "" });

    const texte = (data.content || []).filter((b) => b.type === "text").map((b) => b.text).join("\n");
    const a = texte.indexOf("{"), b = texte.lastIndexOf("}");
    if (a === -1 || b === -1) return res.status(200).json({ items: [] });

    const parsed = JSON.parse(texte.slice(a, b + 1));
    const cats = CATEGORIES.split(", ");
    const items = (Array.isArray(parsed.items) ? parsed.items : []).slice(0, 40).map((it) => ({
      label: clampStr(it.label, 60) || "Sans nom",
      amount: Math.abs(Number(it.amount)) || 0,
      kind: ["debit", "manual", "income"].includes(it.kind) ? it.kind : "debit",
      freq: ["monthly", "weekly", "quarterly", "semiannual", "yearly", "once"].includes(it.freq) ? it.freq : "monthly",
      day: Math.max(1, Math.min(31, Number(it.day) || 1)),
      anchorMonth: Math.max(0, Math.min(11, Number(it.anchorMonth) || 0)),
      category: cats.includes(it.category) ? it.category : "autre",
      note: clampStr(it.note, 120),
    })).filter((it) => it.amount > 0);

    return res.status(200).json({ items });
  } catch (e) {
    return res.status(500).json({ error: "Lecture impossible", detail: String((e && e.message) || e) });
  }
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });

  const body = req.body || {};
  const action = body.action || "set";

  // ─── Appel de QStash : envoi de la notification du jour ───
  // Traité avant le contrôle d'origine (QStash n'envoie pas d'en-tête Origin)
  // et protégé par le secret partagé, que le navigateur ne connaît jamais.
  if (action === "push") {
    try {
      if (body.secret !== SEND_SECRET) return res.status(401).json({ error: "non autorisé" });
      if (!body.subscription) return res.status(400).json({ error: "pas d'abonnement" });

      const notif = composeNotification(body, todayLocal(Number(body.tzOffset || 0)));
      if (!notif) return res.status(200).json({ ok: true, skipped: "rien à signaler" });

      await webpush.sendNotification(body.subscription, JSON.stringify({
        title: notif.title, body: notif.body, tag: "echeance-jour", url: "/budget/",
      }));
      return res.status(200).json({ ok: true });
    } catch (e) {
      // 200 malgré l'erreur : sinon QStash retente en boucle sur un abonnement expiré.
      return res.status(200).json({ ok: false, error: String((e && e.message) || e) });
    }
  }

  // origine autorisée (opt-in, même convention que api/extract.js)
  const allowed = (process.env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (allowed.length) {
    const src = req.headers.origin || req.headers.referer || "";
    if (src && !allowed.some((a) => src.startsWith(a))) {
      return res.status(403).json({ error: "Origine non autorisée" });
    }
  }

  try {
    const { scheduleId = null, subscription = null, hour = 8, minute = 0 } = body;
    const data = sanitize(body.data);

    if (action === "clear") {
      await supprimerPlanification(scheduleId);
      return res.status(200).json({ ok: true });
    }

    // ─── Scan d'une capture (écran Abonnements iOS/Android, relevé bancaire) ───
    if (action === "scan") return scanImage(body, res);

    if (!subscription) return res.status(400).json({ error: "abonnement push manquant" });

    // ─── Envoi immédiat (bouton « Tester la notification ») ───
    if (action === "test") {
      const notif = composeNotification({ ...data, quietIfEmpty: false }, todayLocal(data.tzOffset));
      await webpush.sendNotification(subscription, JSON.stringify({
        title: notif.title, body: notif.body, tag: "echeance-test", url: "/budget/",
      }));
      return res.status(200).json({ ok: true, preview: notif });
    }

    // ─── Planification quotidienne ───
    if (!QSTASH_URL || !QSTASH_TOKEN || !BASE_URL) {
      return res.status(500).json({ error: "QStash non configuré sur le serveur" });
    }

    // L'heure est choisie en heure locale ; QStash raisonne en UTC.
    // getTimezoneOffset() vaut UTC−local en minutes, donc : minutesUTC = minutesLocales + offset.
    const h = Math.max(0, Math.min(23, Math.round(Number(hour))));
    const m = Math.max(0, Math.min(59, Math.round(Number(minute))));
    const utcMin = ((h * 60 + m + data.tzOffset) % 1440 + 1440) % 1440;
    const cron = `${utcMin % 60} ${Math.floor(utcMin / 60)} * * *`;

    await supprimerPlanification(scheduleId);          // une seule planification par appareil

    const dest = `${BASE_URL}/api/budget`;             // QStash rappellera ce même endpoint
    const r = await qstash(`/v2/schedules/${dest}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Upstash-Cron": cron },
      body: JSON.stringify({ ...data, action: "push", subscription, secret: SEND_SECRET }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return res.status(500).json({ error: "planification échouée", detail: d });

    return res.status(200).json({ ok: true, scheduleId: d.scheduleId || d.scheduleID || null, cron });
  } catch (e) {
    return res.status(500).json({ error: "erreur serveur", detail: String((e && e.message) || e) });
  }
}
