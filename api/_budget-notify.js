// api/_budget-notify.js — rédaction du texte de la notification quotidienne.
// Partagé par les actions « push » (planifiée) et « test » de api/budget.js.
import { addDays, findOverdraft, itemsOn, money, occursOn, paidKey } from "./_budget-core.js";

const JOURS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];

// « demain », « jeudi », « dans 5 jours » — un repère lisible sans lire la date.
function quand(fromDate, toDate) {
  const diff = Math.round((Date.parse(toDate) - Date.parse(fromDate)) / 86400000);
  if (diff <= 0) return "aujourd'hui";
  if (diff === 1) return "demain";
  if (diff <= 6) return JOURS[new Date(toDate + "T00:00:00Z").getUTCDay()];
  return `dans ${diff} jours`;
}

// « Netflix 13,49 € · EDF 89 € · +2 autres »
function ligne(items, currency, locale, max = 3) {
  const shown = items.slice(0, max).map((it) => `${it.label} ${money(it.amount, currency, locale)}`);
  const rest = items.length - shown.length;
  if (rest > 0) shown.push(`+${rest} autre${rest > 1 ? "s" : ""}`);
  return shown.join(" · ");
}

const somme = (list) => list.reduce((t, it) => t + Number(it.amount || 0), 0);

// Construit { title, body }. Renvoie null s'il n'y a rien à dire et que
// l'utilisateur a demandé le silence les jours vides.
export function composeNotification(data, today) {
  const {
    items = [], paid = [], currency = "EUR", locale = "fr-FR",
    shiftWeekend = false, aheadDays = 7, quietIfEmpty = true,
    solde = null, soldeDate = null, seuil = 0, alerteJours = 3, premium = false,
  } = data || {};

  const paidSet = new Set(paid);
  const nonRegle = (it, date) => !(it.kind === "manual" && paidSet.has(paidKey(it.id, date)));

  const dujour = itemsOn(items, today, shiftWeekend).filter((it) => nonRegle(it, today));
  const debits = dujour.filter((it) => it.kind === "debit");
  const manuels = dujour.filter((it) => it.kind === "manual");
  const revenus = dujour.filter((it) => it.kind === "income");

  // ── Le Bouclier : l'alerte de découvert passe avant tout le reste ──
  // C'est la seule notification qui part même un jour sans échéance : rater
  // celle-là coûte des frais d'incident à l'utilisateur.
  let alerte = null;
  if (premium && solde !== null && solde !== "") {
    const d = findOverdraft(items, { solde, soldeDate, shiftWeekend, seuil }, today, 60);
    if (d && d.joursRestants <= Math.max(1, Number(alerteJours) || 3)) alerte = d;
  }

  const lignes = [];
  if (alerte) {
    lignes.push(`Il te manque ${money(alerte.manque, currency, locale)} pour tenir jusqu'au ${
      new Date(alerte.date + "T00:00:00Z").getUTCDate()}.`);
  }
  if (manuels.length) lignes.push(`💳 À payer : ${ligne(manuels, currency, locale)}`);
  if (debits.length) lignes.push(`🏦 Prélevé : ${ligne(debits, currency, locale)}`);
  if (revenus.length) lignes.push(`💰 Reçu : ${ligne(revenus, currency, locale)}`);

  // Rappels anticipés : les échéances qui demandent à être annoncées J-N.
  const anticipes = [];
  for (const it of items) {
    const n = Number(it.notifyDaysBefore || 0);
    if (n <= 0) continue;
    const cible = addDays(today, n);
    if (occursOn(it, cible, shiftWeekend) && nonRegle(it, cible)) anticipes.push({ it, date: cible });
  }
  for (const { it, date } of anticipes.slice(0, 2)) {
    lignes.push(`⏳ ${quand(today, date)} : ${it.label} ${money(it.amount, currency, locale)}`);
  }

  if (alerte) {
    return {
      title: `⚠️ Découvert prévu ${quand(today, alerte.date)} : ${money(alerte.solde, currency, locale)}`,
      body: lignes.join("\n"),
      urgent: true,
    };
  }

  // Journée vide : on se tait, ou on annonce la prochaine échéance.
  if (!dujour.length && !anticipes.length) {
    if (quietIfEmpty) return null;
    let prochain = null;
    for (let i = 1; i <= Math.max(1, aheadDays) && !prochain; i++) {
      const date = addDays(today, i);
      const list = itemsOn(items, date, shiftWeekend).filter((it) => nonRegle(it, date));
      if (list.length) prochain = { date, list };
    }
    return {
      title: "Rien ne part aujourd'hui ✅",
      body: prochain
        ? `Prochaine échéance ${quand(today, prochain.date)} : ${ligne(prochain.list, currency, locale)}`
        : `Aucune échéance dans les ${aheadDays} prochains jours.`,
    };
  }

  // Rien aujourd'hui mais un rappel anticipé : le titre parle de ce qui arrive.
  if (!dujour.length) {
    const { it, date } = anticipes[0];
    return {
      title: `À prévoir ${quand(today, date)} : ${money(it.amount, currency, locale)}`,
      body: lignes.join("\n"),
    };
  }

  const sortant = somme(debits) + somme(manuels);
  const titre = sortant > 0
    ? `Aujourd'hui : ${money(sortant, currency, locale)}${manuels.length ? ` · ${manuels.length} à payer` : ""}`
    : `Aujourd'hui : ${money(somme(revenus), currency, locale)} reçus`;

  return { title: titre, body: lignes.join("\n") };
}
