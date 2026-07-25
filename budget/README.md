# échéance. — ce qui part de ton compte

App sœur de **mise.** dans ce dépôt, servie sous `/budget/`.

Tu enregistres tes prélèvements, tes paiements à faire et tes revenus récurrents ;
chaque matin, **une notification te dit ce qui va quitter ton compte aujourd'hui**
et **ce que tu dois payer toi-même** — même application fermée.

## Ce que ça fait

| | |
|---|---|
| ☀️ **Aujourd'hui** | Le montant qui part aujourd'hui, séparé en « à payer toi-même » / « prélevé automatiquement » / « reçu ». Case à cocher pour marquer un paiement comme réglé, puis les 7 prochains jours. |
| 📈 **Solde projeté** | À partir de ton solde actuel, la courbe de ce qu'il te restera sur 30 jours, avec alerte si tu passes dans le rouge et la date du point bas. |
| 🗓️ **Calendrier** | Vue mensuelle : montant et pastilles par jour, totaux prélevé / à payer / reçu du mois, détail au clic. |
| 📋 **Échéances** | Toutes tes lignes triées par prochaine occurrence, avec le coût mensuel moyen (une assurance annuelle compte pour 1/12) et le reste à vivre. |
| 🔔 **Rappel quotidien** | Notification push à l'heure de ton choix, recalculée au moment de l'envoi. Rappel anticipé possible par échéance (J-1 à J-7). |

**Fréquences gérées** : mensuelle, hebdomadaire, trimestrielle, semestrielle, annuelle, ponctuelle.
Le 31 d'un mois court retombe sur le dernier jour (28/29/30). Option « décaler les week-ends »
pour coller au comportement réel de la banque. Dates de début et de fin par échéance
(pratique pour un crédit qui se termine), mise en pause, note, catégorie.

## Fichiers

- `budget/index.html` — toute l'app (HTML + CSS + JS vanilla, aucune dépendance, aucun build).
- `budget/sw.js` — service worker de portée `/budget/` : cache réseau-d'abord + réception des push.
- `budget/manifest.json`, `budget/icon-*.png` — PWA installable (icône maskable incluse).

### Backend (dossier `api/`)
- `api/_budget-core.js` — moteur de récurrence (dates, fréquences, décalage week-end).
- `api/_budget-notify.js` — rédaction du texte de la notification.
- `api/budget.js` — endpoint unique, quatre actions : `set` / `clear` (planification quotidienne),
  `test` (envoi immédiat) et `push` (appelée par QStash chaque jour, protégée par `SEND_SECRET`).

> **Pourquoi un seul fichier** : le plan Vercel Hobby limite un déploiement à **12 fonctions
> serverless** et le dépôt en comptait déjà 11. Séparer planification et envoi faisait échouer
> tout le déploiement (`exceeded_serverless_functions_per_deployment`). Les fichiers préfixés
> par `_` ne comptent pas comme des routes. **Le projet est désormais pile à 12** : ajouter une
> fonction ailleurs cassera le déploiement tant qu'on n'aura pas regroupé d'autres endpoints
> (les trois `*-push.js` de mise. sont les candidats évidents) ou basculé sur un plan Pro.

## Où vivent les données

**Sur le téléphone, dans le `localStorage`** — pas de compte, pas de base de données, rien à
administrer. Deux conséquences à connaître :

1. **Pas de synchronisation entre appareils.** Un export/import JSON est prévu dans les réglages ;
   pense à faire une sauvegarde de temps en temps (vider les données du navigateur efface tout).
2. **La notification doit pouvoir être calculée sans l'app.** C'est la planification QStash
   elle-même qui transporte tes échéances : à chaque modification, l'app supprime l'ancienne
   planification et en recrée une à jour. Le secret d'envoi (`SEND_SECRET`) est injecté côté
   serveur, jamais par le navigateur.

## Variables d'environnement (Vercel)

**Aucune nouvelle variable.** Tout est déjà en place pour les push de mise. :
`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `SEND_SECRET`, `QSTASH_URL`, `QSTASH_TOKEN`,
`PUBLIC_BASE_URL`, et `ALLOWED_ORIGINS` (optionnel) qui protège aussi `/api/budget-schedule`.

La clé VAPID publique est la même que celle de mise. (même serveur applicatif) ; les
abonnements push restent distincts car la portée du service worker diffère (`/budget/` vs `/`).

## Mise en ligne

1. Push sur `main` → Vercel déploie.
2. Ouvre `https://<ton-domaine>/budget/`.
3. **Ajoute l'app à l'écran d'accueil** (indispensable sur iPhone : sans installation, iOS
   refuse les notifications web — l'app te l'affiche si elle détecte le cas).
4. Réglages → active « Notification chaque jour », choisis l'heure, puis « Tester la notification ».

## Limites connues

- **Saisie manuelle** : l'app ne se connecte pas à ta banque. Un vrai lien bancaire impose un
  agrégateur agréé (Bridge, Powens, GoCardless Bank Account Data) avec contrat et KYC — hors
  sujet pour cette version. Tes échéances récurrentes se saisissent une fois et ne bougent plus.
- **Heure d'été / fuseau** : la planification QStash est posée en UTC, calculée depuis le
  décalage de ton téléphone. Au changement d'heure, le rappel se décale d'une heure jusqu'à
  la prochaine ouverture de l'app, qui le réaligne automatiquement.
- **Un appareil = une planification.** Installer l'app sur un second téléphone crée un second
  rappel, avec les données de ce téléphone-là.
- **Moteur dupliqué** : `api/_budget-core.js` et la section « moteur de récurrence » de
  `budget/index.html` sont identiques par nécessité (le front n'a pas de build). Toute
  correction doit être reportée des deux côtés — un test de parité existe et couvre
  ~520 000 combinaisons date × fréquence.
