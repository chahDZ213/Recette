// api/budget-schedule.js — planification (et test) du rappel quotidien des échéances.
//
// L'app n'a pas de base de données : c'est la planification QStash elle-même qui
// transporte les échéances. Chaque modification côté app recrée la planification
// (supprime l'ancienne, en crée une nouvelle) avec les données à jour.
//
// Actions : "set" (créer/remplacer), "clear" (supprimer), "test" (envoyer tout de suite).
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
  };
}

async function qstash(path, init = {}) {
  return fetch(`${QSTASH_URL}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${QSTASH_TOKEN}`, ...(init.headers || {}) },
  });
}

async function supprimer(scheduleId) {
  if (!scheduleId) return;
  try { await qstash(`/v2/schedules/${encodeURIComponent(scheduleId)}`, { method: "DELETE" }); } catch {}
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Méthode non autorisée" });

  // origine autorisée (opt-in, même convention que api/extract.js)
  const allowed = (process.env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  if (allowed.length) {
    const src = req.headers.origin || req.headers.referer || "";
    if (src && !allowed.some((a) => src.startsWith(a))) {
      return res.status(403).json({ error: "Origine non autorisée" });
    }
  }

  try {
    const { action = "set", scheduleId = null, subscription = null, hour = 8, minute = 0 } = req.body || {};
    const data = sanitize(req.body?.data);

    if (action === "clear") {
      await supprimer(scheduleId);
      return res.status(200).json({ ok: true });
    }

    if (!subscription) return res.status(400).json({ error: "abonnement push manquant" });

    // Envoi immédiat (bouton « Tester la notification »).
    if (action === "test") {
      const notif = composeNotification({ ...data, quietIfEmpty: false }, todayLocal(data.tzOffset));
      await webpush.sendNotification(subscription, JSON.stringify({
        title: notif.title, body: notif.body, tag: "echeance-test", url: "/budget/",
      }));
      return res.status(200).json({ ok: true, preview: notif });
    }

    if (!QSTASH_URL || !QSTASH_TOKEN || !BASE_URL) {
      return res.status(500).json({ error: "QStash non configuré sur le serveur" });
    }

    // L'heure est choisie en heure locale ; QStash raisonne en UTC.
    // getTimezoneOffset() vaut UTC−local en minutes, donc : minutesUTC = minutesLocales + offset.
    const h = Math.max(0, Math.min(23, Math.round(Number(hour))));
    const m = Math.max(0, Math.min(59, Math.round(Number(minute))));
    const utcMin = ((h * 60 + m + data.tzOffset) % 1440 + 1440) % 1440;
    const cron = `${utcMin % 60} ${Math.floor(utcMin / 60)} * * *`;

    await supprimer(scheduleId);                       // une seule planification par appareil

    const dest = `${BASE_URL}/api/budget-push`;
    const r = await qstash(`/v2/schedules/${dest}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Upstash-Cron": cron },
      body: JSON.stringify({ ...data, subscription, secret: SEND_SECRET }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return res.status(500).json({ error: "planification échouée", detail: d });

    return res.status(200).json({ ok: true, scheduleId: d.scheduleId || d.scheduleID || null, cron });
  } catch (e) {
    return res.status(500).json({ error: "erreur serveur", detail: String((e && e.message) || e) });
  }
}
