// StudyPilot — interface. Toute la logique pédagogique vit dans engine/ (testée à part).
import { PROGRAMME, MATIERES, STATUTS, STATUT_LABEL, toutesNotions } from "./engine/curriculum.js";
import { enregistrer, nouvelEtat, estDue, iso, addDays, parseIso, diffJours } from "./engine/srs.js";
import { moyennesParMatiere, moyenneGenerale, noteNecessaire, simulerBac, mention, COEFS_BAC, moyenne } from "./engine/grades.js";
import { planifier } from "./engine/planner.js";
import { TYPES_ERREUR, NIVEAUX, NIVEAU_LABEL, bilanErreurs, erreurDominante, niveauSuivant } from "./engine/errors.js";
import { charger, sauver, fusionner, uid, fichierPut, fichierGet, fichierDel, ETAT_INITIAL } from "./engine/store.js";

const SB_URL = "https://hpejfttwocclmqdtdiok.supabase.co";
const SB_KEY = "sb_publishable_vXQvAJWpR0kKwQ-Fo9aWLw__0x3B7k5";
let sb = null;
try { sb = window.supabase.createClient(SB_URL, SB_KEY, { auth: { persistSession: true, autoRefreshToken: true, storageKey: "studypilot-auth" } }); } catch {}

let S = charger();
let session = null; // session Supabase
const NOTIONS = toutesNotions();
const N = Object.fromEntries(NOTIONS.map((n) => [n.id, n]));
const MAT = Object.fromEntries(MATIERES.map((m) => [m.id, m]));
const ui = { minutes: 30, seance: null, exo: null, chatLoading: false, page: "aujourdhui" };

// ---------- utilitaires ----------
const h = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (s) => document.querySelector(s);
const fmt = (x, d = 2) => (x == null || isNaN(x) ? "—" : Number(x).toFixed(d).replace(".", ","));
const dateFr = (s) => parseIso(s).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" });
const JOURS = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];
function toast(t) { const e = $("#toast"); e.textContent = t; e.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => e.classList.remove("on"), 2600); }
let syncTimer;
function save() { sauver(S); clearTimeout(syncTimer); syncTimer = setTimeout(pousser, 1500); }
function prog(id) { return S.progression[id] || nouvelEtat(); }
function setStatut(id, statut) { S.progression[id] = { ...prog(id), statut }; save(); }
function trimestre(dateIso) { const m = parseIso(dateIso).getMonth(); return m >= 8 ? 1 : m <= 2 ? 2 : 3; }
function matOptions(sel) { return MATIERES.map((m) => `<option value="${m.id}" ${m.id === sel ? "selected" : ""}>${h(m.nom)}</option>`).join(""); }
function notionOptions(mat, sel) { return NOTIONS.filter((n) => !mat || n.matiere === mat).map((n) => `<option value="${n.id}" ${n.id === sel ? "selected" : ""}>${h(n.chapitreTitre)} — ${h(n.titre)}</option>`).join(""); }
function form(el) { return Object.fromEntries(new FormData(el).entries()); }

// ---------- IA ----------
async function ia(mode, body) {
  if (!sb) throw new Error("Service de compte indisponible");
  const { data } = await sb.auth.getSession();
  const jwt = data.session?.access_token;
  if (!jwt) throw new Error("Connecte-toi (Paramètres) pour utiliser le professeur IA");
  const r = await fetch("/api/studypilot-ai", { method: "POST", headers: { "content-type": "application/json", authorization: "Bearer " + jwt }, body: JSON.stringify({ mode, ...body }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Erreur IA");
  S.usageIA.push({ id: uid(), date: iso(new Date()), mode, ...j.usage });
  save();
  return j.data;
}
function contexteNotion(id) {
  const n = N[id]; if (!n) return "";
  const e = prog(id), b = bilanErreurs(S.tentatives)[id] || {};
  return `Matière : ${MAT[n.matiere].nom}. Chapitre : ${n.chapitreTitre}. Notion : ${n.titre}.
Prérequis : ${n.prerequis.map((p) => `${N[p]?.titre} (${STATUT_LABEL[prog(p).statut]})`).join(", ") || "aucun"}.
Statut actuel : ${STATUT_LABEL[e.statut]}. Historique de scores : ${e.historique.slice(-5).map((x) => x.score).join(", ") || "aucun"}.
Erreurs fréquentes : ${Object.entries(b).map(([k, v]) => `${TYPES_ERREUR[k]}×${v}`).join(", ") || "aucune"}.
${n.utilite ? "Piste d'application concrète : " + n.utilite : ""}`;
}

// ---------- synchro ----------
async function tirer() {
  if (!sb || !session) return;
  const { data, error } = await sb.from("studypilot_state").select("donnees").eq("user_id", session.user.id).maybeSingle();
  if (error) return toast("Synchro impossible : " + error.message);
  S = fusionner(S, data?.donnees); sauver(S); await pousser(); render();
}
async function pousser() {
  if (!sb || !session) return;
  const { error } = await sb.from("studypilot_state").upsert({ user_id: session.user.id, donnees: S, maj_at: new Date().toISOString() });
  if (error) console.warn("synchro", error.message);
}

// ---------- navigation ----------
const PAGES = [
  ["aujourdhui", "☀︎", "Aujourd'hui"], ["programme", "▤", "Programme"], ["prof", "✦", "Professeur IA"],
  ["exercices", "✎", "Exercices"], ["cours", "▣", "Mes cours"], ["agenda", "◷", "Agenda"],
  ["revisions", "↻", "Révisions"], ["resultats", "▲", "Résultats"], ["parametres", "⚙", "Paramètres"],
];
function nav() {
  $("#nav").innerHTML = `<div class="logo">Study<span>Pilot</span></div>` + PAGES.map(([id, ic, t]) => `<a href="#${id}" class="${ui.page === id ? "on" : ""}"><b>${ic}</b>${t}</a>`).join("");
}
window.addEventListener("hashchange", () => { ui.page = location.hash.slice(1) || "aujourdhui"; render(); });

// ---------- pages ----------
const V = {};

V.aujourdhui = () => {
  const plan = planifier(S, ui.minutes);
  const today = iso(new Date());
  const fait = S.sessions.filter((s) => s.date === today).reduce((a, s) => a + s.minutes, 0);
  const prochains = S.devoirs.filter((d) => !d.fait && d.date >= today).sort((a, b) => a.date.localeCompare(b.date)).slice(0, 4);
  if (ui.seance) return seanceView();
  return `<h1>Bonjour 👋</h1><p class="sub">${new Date().toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })} · objectif ${h(S.profil.objectif)}</p>
  <div class="card hero"><h2>Combien de temps as-tu aujourd'hui ?</h2>
    <div class="chips" style="margin-bottom:16px">${[15, 30, 45, 60, 90].map((m) => `<span class="chip ${ui.minutes === m ? "on" : ""}" data-min="${m}">${m} min</span>`).join("")}</div>
    <button class="p big" id="go" ${plan.blocs.length ? "" : "disabled"}>▶ Lancer ma séance (${plan.total} min)</button>
    <p class="small" style="margin:10px 0 0">${fait ? `Déjà ${fait} min de travail aujourd'hui. ` : ""}Le plan se recalcule à chaque ajout de devoir, note, cours ou indisponibilité.</p></div>
  <div class="card"><h2>Ta séance optimisée</h2>${plan.blocs.length ? plan.blocs.map(blocHtml).join("") : `<p class="mut">Rien à planifier : ajoute ton emploi du temps, tes devoirs et indique dans <a href="#programme">Programme</a> les chapitres en cours.</p>`}</div>
  <div class="grid">
    <div class="card"><h2>Prochaines échéances</h2>${prochains.map((d) => `<div class="bloc"><span class="tag ${d.type === "controle" ? "bad" : ""}">${d.type === "controle" ? "Contrôle" : "Devoir"}</span><div class="sp">${h(d.titre)}<div class="small mut">${h(MAT[d.matiere]?.nom)} · ${dateFr(d.date)}</div></div></div>`).join("") || `<p class="mut">Aucune. <a href="#agenda">Ajouter</a></p>`}</div>
    <div class="card"><h2>Révisions dues</h2><div class="kpi">${NOTIONS.filter((n) => estDue(S.progression[n.id])).length}</div><p class="mut small">notions à réactiver pour ne pas les oublier</p><a href="#revisions">Voir →</a></div>
  </div>`;
};
function blocHtml(b) {
  const lab = { controle: ["Contrôle", "bad"], devoir: ["Devoir", ""], revision: ["Révision", "ok"], consolidation: ["Consolidation", "warn"], anticipation: ["Avance", ""], cours_demain: ["Demain", ""] }[b.type];
  return `<div class="bloc"><span class="tag ${lab[1]}">${lab[0]}</span><div class="sp">${h(b.titre)}<div class="small mut">${h(MAT[b.matiere]?.nom)} · ${h(b.raison)}</div></div><b>${b.minutes}′</b></div>`;
}

function seanceView() {
  const s = ui.seance, b = s.blocs[s.i];
  if (!b) {
    const total = s.blocs.reduce((a, x) => a + (x.fait ? x.minutes : 0), 0);
    S.sessions.push({ id: uid(), date: iso(new Date()), minutes: total, blocs: s.blocs.filter((x) => x.fait).map((x) => x.titre) }); save();
    ui.seance = null;
    return `<div class="card hero"><h1>Séance terminée 🎉</h1><p>${total} minutes de travail utile. La régularité fait plus que les longues séances : reviens demain.</p><a class="btn" href="#aujourdhui" onclick="location.reload()">Retour</a></div>`;
  }
  const n = N[b.notion];
  let corps = "";
  if (b.type === "devoir") corps = `<p>Fais ce devoir maintenant. Bloqué ? Demande un indice au <a href="#prof">professeur IA</a> (il ne te donnera pas la réponse).</p><button class="p" data-act="devoir-fait">✓ Devoir terminé</button>`;
  else if (b.type === "controle") corps = `<p>Notions du contrôle : ${(b.notions || []).map((id) => h(N[id]?.titre)).join(", ") || "précise-les dans l'agenda"}.</p><button class="p" data-act="exo-controle">Générer un entraînement niveau contrôle</button>`;
  else if (n) corps = `${b.type === "anticipation" && b.prerequisManquants?.length ? `<p class="tag warn">Prérequis à vérifier : ${b.prerequisManquants.map((p) => h(N[p]?.titre)).join(", ")}</p>` : ""}
    ${n.utilite ? `<p><b>À quoi ça sert :</b> ${h(n.utilite)}</p>` : ""}
    <div class="row"><button class="p" data-act="${b.type === "anticipation" ? "lecon" : "exo"}">${b.type === "anticipation" ? "Découvrir la notion avec l'IA" : "Exercices adaptés (IA)"}</button></div>
    <details style="margin-top:14px"><summary>Sans IA : auto-évaluation</summary><p class="small mut">Refais de mémoire la définition, une formule et un exercice de ton cours, puis évalue-toi honnêtement.</p>
    <div class="row">${[["0.2", "Je ne savais pas"], ["0.6", "À moitié"], ["0.9", "Réussi"]].map(([v, t]) => `<button data-auto="${v}">${t}</button>`).join("")}</div></details>`;
  return `<p class="sub">Bloc ${s.i + 1}/${s.blocs.length} · ${b.minutes} min</p><div class="card"><h1>${h(b.titre)}</h1><p class="mut">${h(MAT[b.matiere]?.nom)} · ${h(b.raison)}</p>${corps}<div id="zone-ia"></div></div>
  <div class="row"><button data-act="suivant">Bloc suivant →</button><button data-act="stop">Arrêter</button></div>`;
}

V.programme = () => {
  const mat = ui.progMat || "maths";
  const themes = PROGRAMME[mat] || [];
  const ordre = S.ordreProf[mat] || [];
  return `<h1>Programme scolaire</h1><p class="sub">Première générale 2026-2027. ${h(MAT[mat].verif)}. Fixe le statut de chaque notion et l'ordre réellement suivi par ton professeur.</p>
  <div class="chips" style="margin-bottom:14px">${Object.keys(PROGRAMME).map((m) => `<span class="chip ${m === mat ? "on" : ""}" data-progmat="${m}">${h(MAT[m].nom)}</span>`).join("")}</div>
  ${ordre.length ? `<div class="card"><h2>Ordre du professeur</h2>${ordre.map((id, i) => `<div class="bloc"><b>${i + 1}.</b><div class="sp">${h(N[id]?.titre)}</div><button class="sm" data-up="${id}">↑</button><button class="sm" data-down="${id}">↓</button><button class="sm" data-unord="${id}">✕</button></div>`).join("")}</div>` : ""}
  ${themes.map((t) => `<div class="card"><h2>${h(t.theme)}</h2>${t.chapitres.map((c) => `<details open><summary>${h(c.titre)}</summary>${c.notions.map((n) => {
    const st = prog(n.id).statut;
    return `<div class="bloc"><div class="sp"><span class="st-${st}">●</span> ${h(n.titre)}${n.prerequis.length ? `<div class="small mut">Prérequis : ${n.prerequis.map((p) => h(N[p]?.titre)).join(", ")}</div>` : ""}</div>
    <select data-statut="${n.id}">${STATUTS.map((s) => `<option value="${s}" ${s === st ? "selected" : ""}>${STATUT_LABEL[s]}</option>`).join("")}</select>
    ${ordre.includes(n.id) ? "" : `<button class="sm" data-ord="${n.id}" title="Ajouter à l'ordre du prof">+ ordre</button>`}</div>`;
  }).join("")}</details>`).join("")}</div>`).join("")}`;
};

V.prof = () => `<h1>Professeur IA</h1><p class="sub">Il t'aide à raisonner : indices, erreurs repérées, autres explications. Il ne fait pas tes devoirs à ta place.</p>
  <div class="card"><div class="row" style="margin-bottom:10px"><select id="chat-notion"><option value="">Notion (optionnel)</option>${notionOptions(null, ui.chatNotion)}</select><span class="sp"></span><button class="sm" id="chat-reset">Nouvelle conversation</button></div>
  <div class="chat" id="chat">${S.chat.map((m) => `<div class="msg ${m.role}">${h(m.content)}</div>`).join("") || `<p class="mut">Exemples : « Je ne comprends pas le discriminant », « Explique la dérivée avec une voiture », « Vérifie mon raisonnement : … »</p>`}${ui.chatLoading ? `<div class="msg assistant mut">…</div>` : ""}</div>
  <form id="chat-form" class="row" style="margin-top:12px"><input name="q" class="sp" placeholder="Pose ta question…" autocomplete="off" required><button class="p" ${ui.chatLoading ? "disabled" : ""}>Envoyer</button></form>
  <div class="row small" style="margin-top:8px"><button type="button" class="sm" data-quick="Je ne comprends pas, réexplique autrement avec un autre exemple.">Explique autrement</button><button type="button" class="sm" data-quick="Donne-moi juste un indice, pas la réponse.">Un indice</button></div></div>`;

V.exercices = () => {
  const e = ui.exo;
  const notion = ui.exoNotion || NOTIONS.find((n) => n.matiere === "maths").id;
  const niv = ui.exoNiveau || niveauSuivant(S.tentatives, notion);
  const dom = erreurDominante(bilanErreurs(S.tentatives), notion);
  let zone = "";
  if (e?.loading) zone = `<p class="mut">Génération en cours…</p>`;
  else if (e?.liste) {
    const x = e.liste[e.i];
    zone = x ? `<div class="card"><div class="row"><span class="tag">${h(NIVEAU_LABEL[x.niveau] || x.niveau)}</span><span class="mut small">Exercice ${e.i + 1}/${e.liste.length}</span></div>
      <p class="pre">${h(x.enonce)}</p>
      ${(x.indices || []).slice(0, e.indices || 0).map((t, k) => `<p class="small"><b>Indice ${k + 1} :</b> ${h(t)}</p>`).join("")}
      ${e.retour ? `<div class="card"><b>Score ${Math.round(e.retour.score * 100)} %</b> ${e.retour.erreurs.map((t) => `<span class="tag warn">${h(TYPES_ERREUR[t])}</span>`).join(" ")}<p class="pre">${h(e.retour.retour)}</p><details><summary>Correction détaillée</summary><p class="pre">${h(x.solution)}</p></details><button class="p" data-act="exo-next">Suivant →</button></div>`
        : `<form id="rep-form"><label>Ta réponse et ton raisonnement</label><textarea name="r" required></textarea><div class="row" style="margin-top:8px"><button class="p" ${e.corr ? "disabled" : ""}>${e.corr ? "Correction…" : "Valider"}</button>${(x.indices || []).length > (e.indices || 0) ? `<button type="button" data-act="indice">Indice</button>` : ""}</div></form>`}</div>`
      : `<div class="card"><h2>Série terminée</h2><p>Résultats enregistrés, révisions replanifiées.</p><button class="p" data-act="exo-cible">Nouvelle série ciblée sur mes erreurs</button></div>`;
  }
  return `<h1>Exercices</h1><p class="sub">Difficulté progressive, corrections vérifiées, analyse de tes erreurs.</p>
  <div class="card"><div class="row"><select id="exo-notion" class="sp">${notionOptions(null, notion)}</select>
  <select id="exo-niveau">${NIVEAUX.map((n) => `<option value="${n}" ${n === niv ? "selected" : ""}>${NIVEAU_LABEL[n]}</option>`).join("")}</select>
  <button class="p" data-act="exo-gen">Générer 3 exercices</button></div>
  ${dom ? `<p class="small mut">Erreur la plus fréquente sur cette notion : <b>${TYPES_ERREUR[dom]}</b> — les exercices la cibleront.</p>` : ""}</div>${zone}
  <div class="card"><h2>Mes erreurs</h2>${erreursTable()}</div>`;
};
function erreursTable() {
  const b = bilanErreurs(S.tentatives); const ids = Object.keys(b);
  if (!ids.length) return `<p class="mut">Aucune erreur enregistrée pour l'instant.</p>`;
  return `<table><tr><th>Notion</th>${Object.values(TYPES_ERREUR).map((t) => `<th class="small">${t}</th>`).join("")}</tr>${ids.map((id) => `<tr><td>${h(N[id]?.titre)}</td>${Object.keys(TYPES_ERREUR).map((k) => `<td>${b[id][k] || ""}</td>`).join("")}</tr>`).join("")}</table>`;
}

V.cours = () => `<h1>Mes cours</h1><p class="sub">Photos de cours, PDF, exercices, contrôles corrigés, bulletins, emploi du temps, captures Pronote. L'IA classe tout ; tu confirmes ce qui est incertain.</p>
  <div class="card"><label>Importer un document (image ou PDF, 10 Mo max)</label><div class="row"><input type="file" id="file" accept="image/*,application/pdf" capture="environment" multiple><select id="file-mat"><option value="">Matière : détection auto</option>${matOptions("")}</select></div><p class="small mut">Le fichier reste sur ton appareil ; seul le résultat de l'analyse est synchronisé avec ton compte.</p></div>
  ${S.documents.filter((d) => d.aConfirmer).map(docConfirm).join("")}
  <div class="card"><h2>Documents classés</h2>${S.documents.filter((d) => !d.aConfirmer).sort((a, b) => b.date.localeCompare(a.date)).map((d) => `<div class="bloc"><span class="tag">${h(d.type)}</span><div class="sp">${h(d.titre || d.nom)}<div class="small mut">${h(MAT[d.matiere]?.nom || "?")} · ${dateFr(d.date)} · ${d.notions.map((id) => h(N[id]?.titre)).join(", ")}</div>${d.resume ? `<div class="small">${h(d.resume)}</div>` : ""}</div><button class="sm" data-open="${d.id}">Ouvrir</button><button class="sm" data-deldoc="${d.id}">✕</button></div>`).join("") || `<p class="mut">Aucun document.</p>`}</div>`;
function docConfirm(d) {
  const a = d.analyse || {};
  return `<div class="card" style="border-color:var(--warn)"><h2>À confirmer : ${h(d.nom)}</h2>${d.erreur ? `<p class="tag bad">${h(d.erreur)}</p><button data-reanalyse="${d.id}">Réessayer l'analyse</button>` : !d.analyse ? `<p class="mut">Analyse en cours…</p>` : `
  <form data-confirm="${d.id}"><div class="row"><div><label>Type</label><select name="type">${["cours", "exercice", "controle", "bulletin", "emploi_du_temps", "devoirs", "pronote", "autre"].map((t) => `<option ${t === a.type ? "selected" : ""}>${t}</option>`).join("")}</select></div>
  <div><label>Matière</label><select name="matiere">${matOptions(d.matiere)}</select></div><div class="sp"><label>Titre</label><input name="titre" value="${h(a.titre)}" style="width:100%"></div></div>
  <p class="small">Confiance de l'analyse : ${Math.round((a.confiance || 0) * 100)} %. ${h(a.resume)}</p>
  ${(a.incertitudes || []).map((q, i) => `<label>❓ ${h(q.question)} <span class="mut">(${h(q.element)})</span></label><input name="inc${i}" style="width:100%">`).join("")}
  ${d.notions.length ? `<p class="small">Notions : ${d.notions.map((id) => h(N[id]?.titre)).join(", ")}</p>` : ""}
  ${(a.notes || []).length ? `<p class="small"><b>Notes détectées :</b></p>${a.notes.map((n, i) => `<label class="row"><input type="checkbox" name="note${i}" checked> ${h(n.intitule || "")} ${h(n.matiere)} : ${n.valeur}/${n.bareme || 20} (coef ${n.coef || 1}) ${h(n.date || "")}</label>`).join("")}` : ""}
  ${(a.devoirs || []).length ? `<p class="small"><b>Devoirs détectés :</b></p>${a.devoirs.map((x, i) => `<label class="row"><input type="checkbox" name="dev${i}" checked> ${h(x.type)} ${h(x.matiere)} : ${h(x.titre)} pour le ${h(x.date)}</label>`).join("")}` : ""}
  ${(a.creneaux || []).length ? `<label class="row"><input type="checkbox" name="edt" checked> Remplacer mon emploi du temps par les ${a.creneaux.length} créneaux détectés</label>` : ""}
  <div class="row" style="margin-top:10px"><button class="p">Confirmer et classer</button><button type="button" data-deldoc="${d.id}">Supprimer</button></div></form>`}</div>`;
}

V.agenda = () => {
  const today = iso(new Date());
  const dev = [...S.devoirs].sort((a, b) => a.date.localeCompare(b.date));
  return `<h1>Agenda et devoirs</h1><p class="sub">Chaque ajout recalcule ta séance du jour.</p>
  <div class="card"><h2>Ajouter un devoir ou un contrôle</h2><form id="dev-form" class="row"><select name="type"><option value="devoir">Devoir</option><option value="controle">Contrôle</option></select><select name="matiere">${matOptions("maths")}</select><input name="titre" placeholder="Intitulé" required class="sp"><input type="date" name="date" required min="${today}"><input type="number" name="minutes" placeholder="min" style="width:70px" min="5"><button class="p">Ajouter</button></form>
  <label>Notions concernées (contrôle) — Ctrl/⌘ pour plusieurs</label><select multiple id="dev-notions" style="width:100%;height:90px">${notionOptions(null)}</select></div>
  <div class="card"><h2>À venir</h2>${dev.filter((d) => d.date >= today || !d.fait).map((d) => `<div class="bloc"><input type="checkbox" data-fait="${d.id}" ${d.fait ? "checked" : ""}><span class="tag ${d.type === "controle" ? "bad" : ""}">${d.type === "controle" ? "Contrôle" : "Devoir"}</span><div class="sp" style="${d.fait ? "text-decoration:line-through;opacity:.6" : ""}">${h(d.titre)}<div class="small mut">${h(MAT[d.matiere]?.nom)} · ${dateFr(d.date)}${d.date < today && !d.fait ? " · <b style='color:var(--bad)'>en retard</b>" : ""}</div></div><button class="sm" data-deldev="${d.id}">✕</button></div>`).join("") || `<p class="mut">Rien.</p>`}</div>
  <div class="card"><h2>Emploi du temps</h2><form id="edt-form" class="row"><select name="jour">${[1, 2, 3, 4, 5, 6].map((j) => `<option value="${j}">${JOURS[j]}</option>`).join("")}</select><input type="time" name="debut" required><input type="time" name="fin" required><select name="matiere">${matOptions("maths")}</select><button>Ajouter</button></form>
  ${[1, 2, 3, 4, 5, 6].map((j) => { const l = S.edt.filter((c) => +c.jour === j).sort((a, b) => a.debut.localeCompare(b.debut)); return l.length ? `<p style="margin:10px 0 2px"><b>${JOURS[j]}</b></p>${l.map((c) => `<div class="small row">${h(c.debut)}–${h(c.fin)} ${h(MAT[c.matiere]?.nom)} <button class="sm" data-deledt="${S.edt.indexOf(c)}">✕</button></div>`).join("")}` : ""; }).join("")}</div>
  <div class="card"><h2>Indisponibilités</h2><form id="ind-form" class="row"><input type="date" name="date" required><input name="motif" placeholder="Motif (sport, sortie…)" class="sp"><button>Ajouter</button></form>
  ${S.indispos.map((x, i) => `<div class="small row">${dateFr(x.date)} — ${h(x.motif)} <button class="sm" data-delind="${i}">✕</button></div>`).join("")}</div>`;
};

V.revisions = () => {
  const lst = NOTIONS.filter((n) => S.progression[n.id]?.historique?.length).sort((a, b) => (prog(a.id).prochaine || "").localeCompare(prog(b.id).prochaine || ""));
  return `<h1>Révisions</h1><p class="sub">Répétition espacée (J+1, J+3, J+7, J+14, J+30, J+60) et rappel actif. Une notion n'est « maîtrisée » qu'après plusieurs réussites espacées.</p>
  <div class="card">${lst.map((n) => { const e = prog(n.id); const due = estDue(e); return `<div class="bloc"><span class="st-${e.statut}">●</span><div class="sp">${h(n.titre)}<div class="small mut">${h(MAT[n.matiere].nom)} · ${STATUT_LABEL[e.statut]} · ${e.historique.length} passage(s) · prochain : ${e.prochaine ? dateFr(e.prochaine) : "—"}</div></div>${due ? `<span class="tag warn">À revoir</span>` : ""}<button class="sm" data-revexo="${n.id}">S'entraîner</button></div>`; }).join("") || `<p class="mut">Aucune notion travaillée. Lance une séance ou des exercices.</p>`}</div>`;
};

V.resultats = () => {
  const tri = ui.tri || 0;
  const pm = moyennesParMatiere(S.notes, tri || null);
  const gen = moyenneGenerale(pm);
  const par = [1, 2, 3].map((t) => moyenneGenerale(moyennesParMatiere(S.notes, t)));
  const minutes7 = S.sessions.filter((s) => diffJours(parseIso(s.date), new Date()) < 7).reduce((a, s) => a + s.minutes, 0);
  const lacunes = NOTIONS.filter((n) => prog(n.id).statut === "a_consolider").sort((a, b) => MAT[b.matiere].prio - MAT[a.matiere].prio).slice(0, 6);
  const bac = simulerBac(S.bac);
  const chap = {};
  for (const n of NOTIONS) { const c = (chap[n.chapitre] ||= { t: n.chapitreTitre, m: n.matiere, s: 0, k: 0 }); c.k++; c.s += { maitrisee: 1, etudiee: 0.6, en_cours: 0.4, decouverte: 0.3, a_consolider: 0.2 }[prog(n.id).statut] || 0; }
  return `<h1>Résultats et objectifs</h1><p class="sub">Moyennes calculées comme Pronote : notes ramenées sur 20 et pondérées par leur coefficient.</p>
  <div class="grid"><div class="card"><div class="mut small">Moyenne générale ${tri ? "T" + tri : "annuelle"}</div><div class="kpi">${fmt(gen)}</div></div>
  <div class="card"><div class="mut small">Évolution trimestrielle</div><div class="kpi small" style="font-size:18px">${par.map((x, i) => `T${i + 1} ${fmt(x)}`).join(" · ")}</div></div>
  <div class="card"><div class="mut small">Travail (7 derniers jours)</div><div class="kpi">${Math.floor(minutes7 / 60)} h ${minutes7 % 60}</div></div></div>
  <div class="card"><div class="row"><h2 class="sp">Par matière</h2><div class="chips">${[0, 1, 2, 3].map((t) => `<span class="chip ${t === tri ? "on" : ""}" data-tri="${t}">${t ? "T" + t : "Année"}</span>`).join("")}</div></div>
  <table><tr><th>Matière</th><th>Moyenne</th><th>Objectif</th><th>Note nécessaire au prochain devoir (coef 1)</th></tr>
  ${MATIERES.filter((m) => pm[m.id] != null || S.profil.cibles[m.id]).map((m) => { const notes = S.notes.filter((n) => n.matiere === m.id && (!tri || n.trimestre === tri)); const c = S.profil.cibles[m.id]; const nn = c && notes.length ? noteNecessaire(notes, c) : null;
    return `<tr><td>${h(m.nom)}</td><td><b>${fmt(pm[m.id])}</b></td><td><input type="number" step="0.5" min="0" max="20" style="width:70px" data-cible="${m.id}" value="${c ?? ""}"></td><td>${nn == null ? "—" : nn > 20 ? "objectif hors de portée en 1 note" : fmt(Math.max(0, nn), 1)}</td></tr>`; }).join("")}</table></div>
  <div class="card"><h2>Ajouter une note</h2><form id="note-form" class="row"><select name="matiere">${matOptions("maths")}</select><input name="intitule" placeholder="Intitulé" class="sp"><input type="number" name="valeur" step="0.25" min="0" placeholder="Note" required style="width:80px"><span>/</span><input type="number" name="bareme" value="20" min="1" style="width:70px"><input type="number" name="coef" value="1" step="0.5" min="0" style="width:70px" title="coef"><input type="date" name="date" value="${iso(new Date())}" required><button class="p">Ajouter</button></form>
  <details style="margin-top:10px"><summary>Toutes les notes (${S.notes.length})</summary>${[...S.notes].sort((a, b) => b.date.localeCompare(a.date)).map((n) => `<div class="small row">${dateFr(n.date)} · ${h(MAT[n.matiere]?.nom)} · ${h(n.intitule)} : <b>${n.valeur}/${n.bareme}</b> coef ${n.coef} <button class="sm" data-delnote="${n.id}">✕</button></div>`).join("")}</details></div>
  <div class="grid"><div class="card"><h2>Lacunes prioritaires</h2>${lacunes.map((n) => `<div class="small">⚠︎ ${h(n.titre)} <span class="mut">(${h(MAT[n.matiere].nom)})</span></div>`).join("") || `<p class="mut">Aucune lacune identifiée.</p>`}</div>
  <div class="card"><h2>Niveau par chapitre</h2>${Object.values(chap).filter((c) => ["maths", "pc", "si"].includes(c.m)).map((c) => `<div class="small">${h(c.t)}</div><div class="bar" style="margin-bottom:6px"><i style="width:${Math.round((c.s / c.k) * 100)}%"></i></div>`).join("")}</div></div>
  <div class="card"><h2>Appréciations</h2><form id="app-form" class="row"><select name="trimestre"><option>1</option><option>2</option><option>3</option></select><select name="matiere">${matOptions("maths")}</select><input name="texte" class="sp" placeholder="Appréciation du professeur" required><button>Ajouter</button></form>
  ${S.appreciations.map((a, i) => `<div class="small row">T${a.trimestre} · ${h(MAT[a.matiere]?.nom)} : « ${h(a.texte)} » <button class="sm" data-delapp="${i}">✕</button></div>`).join("")}</div>
  <div class="card"><h2>Simulation du bac</h2><p class="small mut">Saisis tes notes réelles ou espérées (contrôle continu = moyenne annuelle). Les cases vides sont ignorées.</p>
  <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr))">${COEFS_BAC.map((x) => `<label>${h(x.nom)} (coef ${x.coef})<input type="number" step="0.1" min="0" max="20" data-bac="${x.id}" value="${S.bac[x.id] ?? ""}" style="width:100%"></label>`).join("")}</div>
  ${bac ? `<p><b>Moyenne simulée : ${fmt(bac.moyenne)}</b> — ${mention(bac.moyenne)} <span class="mut small">(sur ${Math.round(bac.couverture * 100)} % des coefficients)</span></p>` : ""}
  <p class="small mut">⚠︎ Ceci est une estimation, pas une prévision : elle ne garantit en rien une admission en BUT GEII sur Parcoursup, où les dossiers sont étudiés au cas par cas (notes de première et terminale en maths, PC et spécialités, appréciations, projet de formation motivé). Coefficients à vérifier sur Éduscol.</p></div>`;
};

V.parametres = () => {
  const cout = S.usageIA.reduce((a, u) => a + (u.cout || 0), 0);
  const mois = iso(new Date()).slice(0, 7);
  const coutMois = S.usageIA.filter((u) => u.date.startsWith(mois)).reduce((a, u) => a + (u.cout || 0), 0);
  return `<h1>Paramètres</h1>
  <div class="card"><h2>Compte et sauvegarde</h2>${session ? `<p>Connecté : <b>${h(session.user.email)}</b>. Progression synchronisée automatiquement.</p><div class="row"><button data-act="sync">Synchroniser maintenant</button><button data-act="logout">Se déconnecter</button></div>`
    : `<p class="small mut">Le compte sauvegarde ta progression dans le cloud (données protégées par compte, accès limité à toi) et active le professeur IA.</p><form id="login-form" class="row"><input type="email" name="email" placeholder="E-mail" required autocomplete="email"><input type="password" name="pw" placeholder="Mot de passe (8+ car.)" minlength="8" required autocomplete="current-password"><button class="p">Se connecter</button><button type="button" data-act="signup">Créer un compte</button></form>`}</div>
  <div class="card"><h2>Objectif</h2><input id="objectif" value="${h(S.profil.objectif)}" style="width:100%"></div>
  <div class="card"><h2>Consommation IA</h2><p>Ce mois-ci : <b>${coutMois.toFixed(3)} $</b> · total : ${cout.toFixed(3)} $ · ${S.usageIA.length} requêtes</p>
  <table><tr><th>Mode</th><th>Requêtes</th><th>Tokens (entrée/sortie)</th><th>Coût</th></tr>${Object.entries(S.usageIA.reduce((a, u) => { const x = (a[u.mode] ||= { n: 0, i: 0, o: 0, c: 0 }); x.n++; x.i += u.input || 0; x.o += u.output || 0; x.c += u.cout || 0; return a; }, {})).map(([m, x]) => `<tr><td>${m}</td><td>${x.n}</td><td>${x.i} / ${x.o}</td><td>${x.c.toFixed(3)} $</td></tr>`).join("")}</table></div>
  <div class="card"><h2>Données</h2><div class="row"><button data-act="export">Exporter (JSON)</button><label class="btn" style="margin:0;color:var(--ink)">Importer<input type="file" id="import" accept="application/json" hidden></label><button data-act="reset" style="color:var(--bad)">Tout effacer sur cet appareil</button></div></div>`;
};

// ---------- rendu ----------
function render() {
  nav();
  $("#main").innerHTML = (V[ui.page] || V.aujourdhui)();
  const c = $("#chat"); if (c) c.scrollTop = c.scrollHeight;
}

// ---------- actions ----------
document.addEventListener("click", async (ev) => {
  const t = ev.target.closest("[data-min],[data-act],[data-progmat],[data-ord],[data-up],[data-down],[data-unord],[data-auto],[data-tri],[data-deldev],[data-deledt],[data-delind],[data-delnote],[data-delapp],[data-deldoc],[data-open],[data-revexo],[data-reanalyse],[data-quick]");
  if (!t) return;
  const d = t.dataset;
  if (d.min) { ui.minutes = +d.min; return render(); }
  if (d.progmat) { ui.progMat = d.progmat; return render(); }
  if (d.tri) { ui.tri = +d.tri; return render(); }
  if (d.quick) { $("#chat-form [name=q]").value = d.quick; return; }
  const ordre = (m) => (S.ordreProf[m] ||= []);
  if (d.ord) { ordre(N[d.ord].matiere).push(d.ord); save(); return render(); }
  if (d.unord) { const o = ordre(N[d.unord].matiere); o.splice(o.indexOf(d.unord), 1); save(); return render(); }
  if (d.up || d.down) { const id = d.up || d.down, o = ordre(N[id].matiere), i = o.indexOf(id), j = d.up ? i - 1 : i + 1; if (j >= 0 && j < o.length) [o[i], o[j]] = [o[j], o[i]]; save(); return render(); }
  if (d.deldev) { S.devoirs = S.devoirs.filter((x) => x.id !== d.deldev); S.supprimes.push(d.deldev); save(); return render(); }
  if (d.delnote) { S.notes = S.notes.filter((x) => x.id !== d.delnote); S.supprimes.push(d.delnote); save(); return render(); }
  if (d.deledt) { S.edt.splice(+d.deledt, 1); save(); return render(); }
  if (d.delind) { S.indispos.splice(+d.delind, 1); save(); return render(); }
  if (d.delapp) { S.appreciations.splice(+d.delapp, 1); save(); return render(); }
  if (d.deldoc) { const doc = S.documents.find((x) => x.id === d.deldoc); if (doc?.fichierId) await fichierDel(doc.fichierId).catch(() => {}); S.documents = S.documents.filter((x) => x.id !== d.deldoc); S.supprimes.push(d.deldoc); save(); return render(); }
  if (d.open) { const doc = S.documents.find((x) => x.id === d.open); const b = doc && await fichierGet(doc.fichierId).catch(() => null); if (!b) return toast("Fichier absent de cet appareil"); window.open(URL.createObjectURL(b)); return; }
  if (d.revexo) { ui.exoNotion = d.revexo; ui.exoNiveau = null; ui.exo = null; location.hash = "exercices"; return; }
  if (d.reanalyse) { const doc = S.documents.find((x) => x.id === d.reanalyse); doc.erreur = null; render(); return analyser(doc); }
  if (d.auto) { const b = ui.seance.blocs[ui.seance.i]; noterNotion(b.notion, +d.auto, b.type === "anticipation" ? "anticipation" : "lycee", "application", []); b.fait = true; ui.seance.i++; toast("Enregistré, prochaine révision planifiée"); return render(); }
  switch (d.act) {
    case "go": break;
    case "suivant": ui.seance.blocs[ui.seance.i].fait = true; ui.seance.i++; return render();
    case "stop": ui.seance.blocs = ui.seance.blocs.slice(0, ui.seance.i); return render();
    case "devoir-fait": { const b = ui.seance.blocs[ui.seance.i]; const dv = S.devoirs.find((x) => x.id === b.ref); if (dv) dv.fait = true; b.fait = true; ui.seance.i++; save(); return render(); }
    case "lecon": return lecon(ui.seance.blocs[ui.seance.i].notion);
    case "exo": case "exo-controle": { const b = ui.seance.blocs[ui.seance.i]; ui.exoNotion = b.notion || b.notions?.[0] || ui.exoNotion; ui.exoNiveau = d.act === "exo-controle" ? "controle" : null; ui.exo = null; ui.retourSeance = true; location.hash = "exercices"; return genererExos(); }
    case "exo-gen": ui.exoNotion = $("#exo-notion").value; ui.exoNiveau = $("#exo-niveau").value; return genererExos();
    case "exo-cible": ui.exoNiveau = null; return genererExos();
    case "indice": ui.exo.indices = (ui.exo.indices || 0) + 1; return render();
    case "exo-next": ui.exo.i++; ui.exo.retour = null; ui.exo.indices = 0; if (ui.exo.i >= ui.exo.liste.length && ui.retourSeance && ui.seance) { ui.retourSeance = false; ui.seance.blocs[ui.seance.i].fait = true; ui.seance.i++; location.hash = "aujourdhui"; } return render();
    case "export": { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(S, null, 1)], { type: "application/json" })); a.download = `studypilot-${iso(new Date())}.json`; a.click(); return; }
    case "reset": if (confirm("Effacer toutes les données de cet appareil ? (le cloud n'est pas touché)")) { S = ETAT_INITIAL(); sauver(S); render(); } return;
    case "sync": await tirer(); return toast("Synchronisé");
    case "logout": await sb.auth.signOut(); session = null; return render();
    case "signup": { const f = form($("#login-form")); const { error } = await sb.auth.signUp({ email: f.email, password: f.pw }); return toast(error ? error.message : "Compte créé : confirme ton e-mail puis connecte-toi"); }
  }
  if (t.id === "go" || d.act === "go") { ui.seance = { ...planifier(S, ui.minutes), i: 0 }; render(); }
});
$("#main").addEventListener("click", (e) => { if (e.target.id === "go") { ui.seance = { ...planifier(S, ui.minutes), i: 0 }; render(); } if (e.target.id === "chat-reset") { S.chat = []; save(); render(); } });

document.addEventListener("change", async (ev) => {
  const t = ev.target, d = t.dataset;
  if (d.statut) { setStatut(d.statut, t.value); if (t.value === "en_cours") toast("Noté : chapitre commencé en classe"); return; }
  if (d.fait) { const x = S.devoirs.find((y) => y.id === d.fait); x.fait = t.checked; save(); return render(); }
  if (d.cible) { S.profil.cibles[d.cible] = t.value === "" ? undefined : +t.value; save(); return render(); }
  if (d.bac) { if (t.value === "") delete S.bac[d.bac]; else S.bac[d.bac] = +t.value; save(); return render(); }
  if (t.id === "objectif") { S.profil.objectif = t.value; save(); return; }
  if (t.id === "chat-notion") { ui.chatNotion = t.value; return; }
  if (t.id === "exo-notion") { ui.exoNotion = t.value; ui.exoNiveau = null; return render(); }
  if (t.id === "file") { for (const f of t.files) await importer(f, $("#file-mat").value); t.value = ""; return; }
  if (t.id === "import") { try { const j = JSON.parse(await t.files[0].text()); if (!j.version) throw 0; S = fusionner(S, { ...j, maj: Date.now() }); save(); toast("Importé"); render(); } catch { toast("Fichier invalide"); } }
});

document.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target, v = form(f);
  if (f.id === "dev-form") {
    const notions = [...$("#dev-notions").selectedOptions].map((o) => o.value);
    S.devoirs.push({ id: uid(), type: v.type, matiere: v.matiere, titre: v.titre, date: v.date, minutes: v.minutes ? +v.minutes : undefined, notions, fait: false });
    save(); toast("Ajouté — planning recalculé"); return render();
  }
  if (f.id === "edt-form") { S.edt.push({ jour: +v.jour, debut: v.debut, fin: v.fin, matiere: v.matiere }); save(); return render(); }
  if (f.id === "ind-form") { S.indispos.push({ date: v.date, motif: v.motif }); save(); return render(); }
  if (f.id === "note-form") { S.notes.push({ id: uid(), matiere: v.matiere, intitule: v.intitule, valeur: +v.valeur, bareme: +v.bareme || 20, coef: v.coef === "" ? 1 : +v.coef, date: v.date, trimestre: trimestre(v.date) }); save(); toast("Note ajoutée"); return render(); }
  if (f.id === "app-form") { S.appreciations.push({ trimestre: +v.trimestre, matiere: v.matiere, texte: v.texte }); save(); return render(); }
  if (f.id === "login-form") { const { data, error } = await sb.auth.signInWithPassword({ email: v.email, password: v.pw }); if (error) return toast(error.message); session = data.session; await tirer(); return toast("Connecté"); }
  if (f.id === "chat-form") return chat(v.q);
  if (f.id === "rep-form") return corriger(v.r);
  if (f.dataset.confirm) return confirmerDoc(f.dataset.confirm, v);
});

// ---------- flux pédagogiques ----------
function noterNotion(id, score, source, niveau, erreurs) {
  if (!id) return;
  S.progression[id] = enregistrer(prog(id), score, new Date(), source);
  S.tentatives.push({ id: uid(), date: iso(new Date()), notion: id, niveau, score, erreurs });
  save();
}

async function chat(q) {
  S.chat.push({ role: "user", content: q }); ui.chatLoading = true; render();
  try {
    const ctx = ui.chatNotion ? `[Contexte élève]\n${contexteNotion(ui.chatNotion)}\n\n` : "";
    const msgs = S.chat.map((m, i) => (i === S.chat.length - 1 && ctx ? { ...m, content: ctx + m.content } : m));
    const rep = await ia("tuteur", { messages: msgs });
    S.chat.push({ role: "assistant", content: rep });
  } catch (e) { toast(e.message); S.chat.pop(); }
  ui.chatLoading = false; save(); render();
}

async function genererExos() {
  const notion = ui.exoNotion, niveau = ui.exoNiveau || niveauSuivant(S.tentatives, notion);
  const dom = erreurDominante(bilanErreurs(S.tentatives), notion);
  ui.exo = { loading: true }; render();
  try {
    const r = await ia("exercices", { contexte: contexteNotion(notion), prompt: `Génère 3 exercices de niveau « ${NIVEAU_LABEL[niveau]} » (champ niveau = "${niveau}") sur cette notion.${dom ? ` Cible particulièrement l'erreur fréquente : ${TYPES_ERREUR[dom]}.` : ""} Donne 2 à 3 indices gradués par exercice.` });
    ui.exo = { liste: r.exercices.map((x) => ({ ...x, niveau: NIVEAUX.includes(x.niveau) ? x.niveau : niveau })), i: 0, notion };
  } catch (e) { ui.exo = null; toast(e.message); }
  render();
}

async function corriger(rep) {
  const e = ui.exo, x = e.liste[e.i];
  e.corr = true; render();
  try {
    const r = await ia("correction", { prompt: `Énoncé :\n${x.enonce}\n\nSolution attendue :\n${x.solution}\nRéponse attendue : ${x.reponse_attendue}\n\nRéponse de l'élève :\n${rep}\n\nIndices utilisés : ${e.indices || 0}` });
    r.score = Math.max(0, Math.min(1, r.score - 0.1 * (e.indices || 0)));
    e.retour = r;
    noterNotion(e.notion, r.score, prog(e.notion).statut === "non_etudiee" || prog(e.notion).statut === "decouverte" ? "anticipation" : "lycee", x.niveau, r.erreurs);
  } catch (err) { toast(err.message); }
  e.corr = false; render();
}

async function lecon(id) {
  const z = $("#zone-ia"); z.innerHTML = `<p class="mut">Préparation de la leçon…</p>`;
  try {
    const r = await ia("lecon", { contexte: contexteNotion(id), prompt: "Prépare la découverte anticipée de cette notion." });
    ui.exo = { liste: r.exercices.map((x, k) => ({ ...x, niveau: NIVEAUX[Math.min(k, 2)] })), i: 0, notion: id };
    ui.exoNotion = id; ui.retourSeance = true;
    z.innerHTML = `<h2>Utilité</h2><p class="pre">${h(r.utilite)}</p><h2>Cours</h2><p class="pre">${h(r.cours)}</p><h2>Exemple détaillé</h2><p class="pre">${h(r.exemple)}</p>
      <h2>Vérifie ta compréhension</h2>${r.verification.map((q) => `<details><summary>${h(q.question)}</summary><p>${h(q.reponse_attendue)}</p></details>`).join("")}
      <button class="p" style="margin-top:12px" onclick="location.hash='exercices'">Passer aux ${r.exercices.length} exercices progressifs →</button>`;
    if (prog(id).statut === "non_etudiee") setStatut(id, "decouverte");
  } catch (e) { z.innerHTML = `<p class="tag bad">${h(e.message)}</p>`; }
}

// ---------- documents ----------
async function compresser(file) {
  if (!file.type.startsWith("image/")) return file;
  const img = await createImageBitmap(file);
  const k = Math.min(1, 2000 / Math.max(img.width, img.height));
  const c = new OffscreenCanvas(Math.round(img.width * k), Math.round(img.height * k));
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  return c.convertToBlob({ type: "image/jpeg", quality: 0.82 });
}
const b64 = (blob) => new Promise((ok) => { const r = new FileReader(); r.onload = () => ok(r.result.split(",")[1]); r.readAsDataURL(blob); });

async function importer(file, matiere) {
  if (file.size > 10e6) return toast(`${file.name} : trop lourd (10 Mo max)`);
  const blob = await compresser(file).catch(() => file);
  if (blob.size > 3.3e6) return toast(`${file.name} : trop lourd pour l'analyse après compression`);
  const fichierId = uid();
  await fichierPut(fichierId, blob);
  const doc = { id: uid(), nom: file.name, type: "autre", matiere: matiere || "", notions: [], date: iso(new Date()), fichierId, aConfirmer: true };
  S.documents.push(doc); save(); render();
  analyser(doc);
}
async function analyser(doc) {
  try {
    const blob = await fichierGet(doc.fichierId);
    const liste = NOTIONS.filter((n) => !doc.matiere || n.matiere === doc.matiere).map((n) => `${n.id} | ${n.matiere} | ${n.titre}`).join("\n");
    const a = await ia("document", { fichier: { type: blob.type, data: await b64(blob) }, contexte: `Matières : ${MATIERES.map((m) => m.id + "=" + m.nom).join(", ")}.\nNotions (id | matière | titre) :\n${liste}\nAnnée scolaire 2026-2027 ; dates au format AAAA-MM-JJ. Pour l'emploi du temps, jour : 1=lundi … 6=samedi.`, prompt: `Analyse ce document${doc.matiere ? " (matière indiquée : " + doc.matiere + ")" : ""}. Dans "notions", mets uniquement des ids de la liste. Dans "matiere", mets un id de matière.` });
    doc.analyse = a; doc.type = a.type; doc.matiere = MAT[a.matiere] ? a.matiere : doc.matiere; doc.notions = (a.notions || []).filter((id) => N[id]);
    doc.titre = a.titre; doc.resume = a.resume;
    // Sûr et confiant → classement direct ; sinon confirmation
    if ((a.confiance ?? 0) >= 0.85 && !(a.incertitudes || []).length && !(a.notes || []).length && !(a.devoirs || []).length && !(a.creneaux || []).length) { doc.aConfirmer = false; lierNotions(doc); toast(`Classé : ${a.titre}`); }
  } catch (e) { doc.erreur = e.message; }
  save(); render();
}
function lierNotions(doc) {
  if (doc.type === "cours") for (const id of doc.notions) if (["non_etudiee", "decouverte"].includes(prog(id).statut)) setStatut(id, "en_cours");
}
function confirmerDoc(id, v) {
  const doc = S.documents.find((x) => x.id === id), a = doc.analyse;
  doc.type = v.type; doc.matiere = v.matiere; doc.titre = v.titre;
  doc.precisions = (a.incertitudes || []).map((q, i) => ({ q: q.question, r: v["inc" + i] })).filter((x) => x.r);
  (a.notes || []).forEach((n, i) => { if (v["note" + i] && typeof n.valeur === "number") { const date = /^\d{4}-\d\d-\d\d$/.test(n.date) ? n.date : iso(new Date()); S.notes.push({ id: uid(), matiere: MAT[n.matiere] ? n.matiere : doc.matiere, intitule: n.intitule, valeur: n.valeur, bareme: n.bareme || 20, coef: n.coef || 1, date, trimestre: trimestre(date) }); } });
  (a.devoirs || []).forEach((x, i) => { if (v["dev" + i] && /^\d{4}-\d\d-\d\d$/.test(x.date)) S.devoirs.push({ id: uid(), type: x.type, matiere: MAT[x.matiere] ? x.matiere : doc.matiere, titre: x.titre, date: x.date, fait: false, notions: doc.notions }); });
  if (v.edt && a.creneaux?.length) S.edt = a.creneaux.filter((c) => MAT[c.matiere] && c.jour >= 1 && c.jour <= 6).map((c) => ({ jour: c.jour, debut: c.debut, fin: c.fin, matiere: c.matiere }));
  for (const ap of a.appreciations || []) S.appreciations.push({ trimestre: trimestre(doc.date), matiere: MAT[ap.matiere] ? ap.matiere : doc.matiere, texte: ap.texte });
  doc.aConfirmer = false; lierNotions(doc); save(); toast("Document classé — planning recalculé"); render();
}

// ---------- démarrage ----------
ui.page = location.hash.slice(1) || "aujourdhui";
render();
if (sb) {
  sb.auth.getSession().then(({ data }) => { session = data.session; if (session) tirer(); else render(); });
  sb.auth.onAuthStateChange((_e, s) => { session = s; });
}
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
