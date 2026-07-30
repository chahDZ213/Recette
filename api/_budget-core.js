// api/_budget-core.js — moteur de récurrence des échéances (côté serveur).
//
// ⚠️ Ce moteur est VOLONTAIREMENT DUPLIQUÉ à l'identique dans budget/index.html
//    (section « moteur de récurrence »). Le front n'a pas de build : il ne peut pas
//    importer ce module. Toute correction ici doit être reportée là-bas, sinon la
//    notification quotidienne et l'écran « Aujourd'hui » ne diront plus la même chose.
//
// Une échéance :
//   { id, label, amount, kind: "debit"|"manual"|"income",
//     freq: "once"|"weekly"|"monthly"|"quarterly"|"semiannual"|"yearly",
//     day (1..31), weekday (0..6), anchorMonth (0..11), date ("YYYY-MM-DD"),
//     start, end, paused, notifyDaysBefore, category, note }

// --- dates en texte "YYYY-MM-DD" (aucun fuseau : ce sont des jours civils) ---
export function ymd(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}`;
}
export function parseYmd(s) {
  const [y, m, d] = String(s).split("-").map(Number);
  return new Date(Date.UTC(y, (m || 1) - 1, d || 1));
}
export function addDays(s, n) {
  const d = parseYmd(s);
  d.setUTCDate(d.getUTCDate() + n);
  return ymd(d);
}
export function daysInMonth(year, month) {
  return new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
}

// Jour civil courant chez l'utilisateur, à partir de son décalage (getTimezoneOffset()).
export function todayLocal(tzOffsetMinutes = 0) {
  return ymd(new Date(Date.now() - tzOffsetMinutes * 60000));
}

// Décale au lundi si la date tombe un samedi/dimanche (les banques ne prélèvent pas le week-end).
export function shiftToWorkday(dateStr) {
  const wd = parseYmd(dateStr).getUTCDay();
  if (wd === 6) return addDays(dateStr, 2);
  if (wd === 0) return addDays(dateStr, 1);
  return dateStr;
}

// Le jour du mois demandé, ramené au dernier jour si le mois est trop court (31 → 28/30).
function dayOfMonthClamped(year, month, wanted) {
  return Math.min(Math.max(1, wanted || 1), daysInMonth(year, month));
}

// L'échéance tombe-t-elle ce jour-là ? (avant tout décalage week-end)
function occursOnRaw(item, dateStr) {
  if (!item || item.paused) return false;
  if (item.start && dateStr < item.start) return false;
  if (item.end && dateStr > item.end) return false;

  const d = parseYmd(dateStr);
  const y = d.getUTCFullYear();
  const m = d.getUTCMonth();
  const dom = d.getUTCDate();

  switch (item.freq) {
    case "once":
      return item.date === dateStr;
    case "weekly":
      return d.getUTCDay() === Number(item.weekday ?? 1);
    case "monthly":
      return dom === dayOfMonthClamped(y, m, item.day);
    case "quarterly":
      return ((m - Number(item.anchorMonth || 0)) % 3 + 3) % 3 === 0 && dom === dayOfMonthClamped(y, m, item.day);
    case "semiannual":
      return ((m - Number(item.anchorMonth || 0)) % 6 + 6) % 6 === 0 && dom === dayOfMonthClamped(y, m, item.day);
    case "yearly":
      return m === Number(item.anchorMonth || 0) && dom === dayOfMonthClamped(y, m, item.day);
    default:
      return false;
  }
}

// Version « réelle » : applique le décalage week-end si l'option est active.
// On regarde les 3 jours précédents : un prélèvement du samedi remonte au lundi.
export function occursOn(item, dateStr, shiftWeekend) {
  if (!shiftWeekend) return occursOnRaw(item, dateStr);
  const wd = parseYmd(dateStr).getUTCDay();
  if (wd === 0 || wd === 6) return false;            // rien ne tombe un week-end
  for (let back = 0; back <= 2; back++) {
    const src = addDays(dateStr, -back);
    if (back > 0) {
      const swd = parseYmd(src).getUTCDay();
      if (swd !== 0 && swd !== 6) continue;          // seul un week-end se décale
    }
    if (occursOnRaw(item, src) && shiftToWorkday(src) === dateStr) return true;
  }
  return false;
}

// Toutes les échéances d'un jour donné, triées : à payer d'abord, puis prélèvements, puis revenus.
const ORDER = { manual: 0, debit: 1, income: 2 };
export function itemsOn(items, dateStr, shiftWeekend) {
  return (items || [])
    .filter((it) => occursOn(it, dateStr, shiftWeekend))
    .sort((a, b) => (ORDER[a.kind] ?? 1) - (ORDER[b.kind] ?? 1) || Number(b.amount || 0) - Number(a.amount || 0));
}

// Les N prochains jours qui portent au moins une échéance.
export function nextOccurrences(items, fromDate, days, shiftWeekend) {
  const out = [];
  for (let i = 0; i < days; i++) {
    const date = addDays(fromDate, i);
    const list = itemsOn(items, date, shiftWeekend);
    if (list.length) out.push({ date, items: list });
  }
  return out;
}

// Clé d'un paiement manuel coché comme réglé (une occurrence = un id + un jour).
export function paidKey(id, dateStr) {
  return `${id}:${dateStr}`;
}

// --- Projection de solde ---------------------------------------------------
// Rejoue les échéances jour par jour à partir du solde constaté. Renvoie un point
// par jour : [{date, solde}], le premier étant le solde avant les mouvements du jour.
export function projectBalance(items, opts, from, days) {
  const { solde, soldeDate, shiftWeekend = false, ignore = [] } = opts || {};
  const exclus = new Set(ignore);
  const actifs = (items || []).filter((it) => !exclus.has(it.id));
  let courant = Number(solde);
  if (!Number.isFinite(courant)) return [];

  const mouvements = (date) => {
    for (const it of itemsOn(actifs, date, shiftWeekend)) {
      if (it.kind === "income") courant += Number(it.amount || 0);
      else courant -= Number(it.amount || 0);
    }
  };

  // Le solde a été constaté à une date passée : on rattrape jusqu'à aujourd'hui.
  if (/^\d{4}-\d{2}-\d{2}$/.test(soldeDate || "") && soldeDate < from) {
    let d = soldeDate;
    for (let n = 0; d < from && n < 400; n++, d = addDays(d, 1)) mouvements(d);
  }

  const pts = [{ date: from, solde: courant }];
  for (let i = 0; i < days; i++) {
    const date = addDays(from, i);
    mouvements(date);
    pts.push({ date, solde: courant });
  }
  return pts;
}

// Premier jour où le solde projeté passe sous le seuil de sécurité.
// Renvoie null si la voie est libre sur toute la période.
export function findOverdraft(items, opts, from, days = 60) {
  const pts = projectBalance(items, opts, from, days);
  if (!pts.length) return null;
  const seuil = Number(opts?.seuil) || 0;

  const franchi = pts.find((p, i) => i > 0 && p.solde < seuil);
  if (!franchi) return null;

  const bas = pts.reduce((m, p) => (p.solde < m.solde ? p : m), pts[0]);
  return {
    date: franchi.date,
    solde: franchi.solde,
    manque: seuil - franchi.solde,          // ce qu'il faudrait ajouter pour tenir
    joursRestants: Math.round((Date.parse(franchi.date) - Date.parse(from)) / 86400000),
    bas,
    seuil,
  };
}

// Formatage monétaire — même rendu côté serveur (notification) et côté app.
export function money(amount, currency = "EUR", locale = "fr-FR") {
  const n = Number(amount || 0);
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency", currency,
      minimumFractionDigits: Number.isInteger(n) ? 0 : 2,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${n.toFixed(2)} ${currency}`;
  }
}
