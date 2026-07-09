# PROJECT_CONTEXT.md — mise.

> **Document de référence pour les assistants IA** (Claude Code = ingénieur développeur principal, ChatGPT = architecture / produit / design / audits).
> À maintenir à jour à chaque grosse modification du projet.
> Dernière mise à jour : 2026-07-09.

---

## 1. Objectif de l'application

**mise.** est une PWA (Progressive Web App) qui transforme **n'importe quelle source de recette** — vidéo YouTube/Shorts, Instagram, TikTok, Facebook, site web (Marmiton, 750g, blogs), lien Google, photo/capture d'écran, ou texte collé — en **recette structurée et interactive** : ingrédients avec quantités ajustables par nombre de personnes, et mode cuisson étape par étape mains-libres.

Positionnement : « La recette, sans le bouton pause. »

## 2. Technologies

| Couche | Techno |
|---|---|
| Frontend | **HTML/CSS/JS vanilla, un seul fichier `index.html`** (~2500 lignes), aucune dépendance ni build |
| PWA | `manifest.json`, `sw.js` (service worker network-first + web push), installable |
| Backend | **Fonctions serverless Vercel** (Node, dossier `api/`) |
| IA | **API Anthropic Claude** (`claude-sonnet-4-6`) : extraction texte, vision (photos/captures), idées, traduction |
| Base de données | **Supabase** (auth email/mot de passe + table `recipes`, données JSON) |
| Transcription vidéo | **Supadata** (transcripts YouTube/TikTok/Insta/Facebook) |
| Métadonnées vidéo | YouTube Data API (optionnel, description) |
| Photos de plats | **Pexels API** (fallback si pas d'og:image) |
| Notifications push | **web-push** (VAPID) + **QStash** (Upstash) pour la planification différée |
| Déploiement | **Vercel**, connecté au dépôt GitHub `chahDZ213/Recette`, auto-deploy sur push `main` |

## 3. Architecture

```
Utilisateur (PWA index.html)
   │  colle un lien / photo / texte
   ▼
POST /api/extract  ──────────────┐
   │                             │
   ├─ URL vidéo → Supadata (transcript) + YouTube API (description)
   ├─ URL site  → fetch de la page (schema.org Recipe + texte + og:image)
   ├─ Image     → Claude Vision
   ├─ Texte     → direct
   │                             │
   ▼                             │
Claude (claude-sonnet-4-6) → JSON structuré {title, baseServings, ingredients[], steps[]}
   │                             │
   ├─ Pexels (photo si absente)  │
   ▼                             ▼
Frontend : affichage recette → Supabase (historique + recettes sauvées, par utilisateur)
   │
   └─ Mode cuisson : minuteurs, voix (SpeechSynthesis), mains-libres (SpeechRecognition),
      push différés (QStash → /api/send-push → web-push)
```

**Format recette (contrat central entre toutes les couches) :**
```json
{
  "title": "...", "baseServings": 4, "image": "https://…",
  "ingredients": [{"name": "farine", "amount": 250, "unit": "g", "category": "Épicerie"}],
  "steps": [{"title": "...", "content": "...", "timerSeconds": 600, "temp": 180, "mode": "four"}],
  "_lang": "fr"
}
```
- `category` ∈ {Frais, Viandes & poissons, Crémerie, Épicerie, Épices, Autre} — **clés internes toujours en français**, traduites à l'affichage.
- `_lang` : langue actuelle du contenu (sert à la traduction automatique).
- Les quantités ne sont **jamais répétées dans les étapes** (pour que l'ajustement des portions reste cohérent).

## 4. Structure des fichiers

```
Recette/
├── index.html          ← TOUTE l'app frontend (HTML + CSS + JS, i18n FR/EN inclus)
├── sw.js               ← service worker (cache network-first + réception push)
├── manifest.json       ← manifeste PWA
├── icon-192.png / icon-512.png
├── package.json        ← seule dépendance : web-push
├── api/
│   ├── extract.js      ← endpoint principal : extraction, vision, idées, frigo, traduction, codes premium
│   ├── schedule-push.js ← planifie un push différé via QStash
│   ├── send-push.js    ← appelé par QStash, envoie le push (protégé par SEND_SECRET)
│   └── cancel-push.js  ← annule un push planifié
├── PROJECT_CONTEXT.md  ← ce fichier
└── README.md
```

**Variables d'environnement Vercel :** `ANTHROPIC_API_KEY`, `SUPADATA_API_KEY`, `YOUTUBE_API_KEY` (opt.), `PEXELS_API_KEY` (opt.), `PREMIUM_CODES`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `SEND_SECRET`, `QSTASH_URL`, `QSTASH_TOKEN`, `PUBLIC_BASE_URL`, `ALLOWED_ORIGINS` (opt., protection API).

## 5. Fonctionnalités terminées

- ✅ Extraction de recettes : YouTube/Shorts, Instagram, TikTok, Facebook, sites web (Marmiton, blogs…), liens Google (`google.com/url?q=…` dépliés), URLs sans `https://`, photo/capture (vision), texte collé, création par IA
- ✅ Portions ajustables (quantités recalculées, fractions ½ ¼ ¾)
- ✅ Mode « Sans balance » (conversions cuillères/verres, bouton coloré quand actif)
- ✅ Mode cuisson : étapes plein écran, minuteurs intégrés, températures, navigation vocale mains-libres (« suivant »), lecture vocale des étapes, wake lock
- ✅ Notifications push de fin de minuteur (même app fermée, via QStash)
- ✅ Comptes utilisateurs (Supabase auth) + historique + recettes sauvées + collections + favoris
- ✅ Liste de courses par catégories (fusion des quantités) + menu de la semaine
- ✅ Idées recettes depuis le frigo (photo ou liste d'ingrédients)
- ✅ Partage de recettes (lien public en lecture seule)
- ✅ i18n FR/EN complet + **traduction automatique de toutes les recettes** (enregistrées, favoris ET historique) au changement de langue de l'app — marqueur `_lang` pour éviter les re-traductions, liste mise à jour en direct, toast de progression
- ✅ Emojis d'ingrédients (~90 ingrédients, détection par mot entier ; pas d'emoji si rien de représentatif — ex. sucre, levure)
- ✅ Thème clair/sombre, notes personnelles, photos personnalisées, gating premium par codes
- ✅ Sécurité : contrôle d'origine API (opt-in `ALLOWED_ORIGINS`), limites de taille des entrées, filtrage des URLs `javascript:`, timeout réseau 75 s

## 6. Fonctionnalités en cours / récemment livrées

- 🔄 Traduction automatique globale au changement de langue — **livrée, à tester en production** (séquentielle, toast de progression `n/total`, persistée dans Supabase)
- 🔄 Animations de chargement rééquilibrées — livrées (messages 2,6 s, rattrapage accéléré quand le serveur a fini)

## 7. Problèmes et points faibles connus

1. **Premium contournable** : le statut est un simple `localStorage.mise_premium="1"`, vérifiable côté client uniquement. À migrer côté serveur (table Supabase + vérification dans `/api/extract`) avant toute monétisation sérieuse.
2. **RLS Supabase à vérifier** : s'assurer que la table `recipes` a des Row Level Security policies (chaque utilisateur ne lit/écrit que ses lignes).
3. **`ALLOWED_ORIGINS` non activé par défaut** : tant que la variable n'est pas définie dans Vercel, l'API est appelable par n'importe quel site (risque de consommation des crédits Anthropic).
4. **`index.html` monolithique (~2500 lignes)** : voulu (zéro build), mais la maintenabilité baisse à mesure que l'app grossit. Si le fichier dépasse ~4000 lignes, envisager un découpage.
5. **Traduction en masse séquentielle** : ~5-10 s par recette ; un utilisateur avec 50 recettes attendra plusieurs minutes (toast de progression, mais pas d'annulation).
6. **YouTube depuis datacenter** : certains transcripts échouent (blocage IP) → fallback « coller la description » proposé à l'utilisateur.
7. **Pas de tests automatisés** ni de CI.

## 8. Prochaines améliorations recommandées

1. Activer `ALLOWED_ORIGINS` dans Vercel (1 minute, gros gain sécurité).
2. Vérifier/activer les RLS Supabase sur `recipes`.
3. Premium côté serveur (Supabase + vérification API).
4. Import/export des recettes (JSON, PDF).
5. Mode hors-ligne complet (recettes sauvées consultables sans réseau — le SW cache déjà les GET, mais les données viennent de Supabase).
6. Onboarding 3 écrans à la première ouverture.
7. Recherche par ingrédient dans ses recettes + filtre par temps de cuisson.
8. Tests E2E basiques (Playwright) sur les parcours critiques : extraction, portions, mode cuisson.

---

## Conventions pour les assistants IA

- **Langue du code et des commentaires : français.** Interface bilingue FR/EN via le dictionnaire `STR` dans `index.html` (toute nouvelle chaîne visible doit exister en FR **et** EN, et être branchée dans `applyLang()`).
- **Aucun framework, aucun build** : tout changement frontend se fait dans `index.html` en vanilla JS. Échapper toute donnée utilisateur avec `esc()` avant `innerHTML`.
- **Ne jamais casser le format recette** (section 3) : c'est le contrat entre extraction, affichage, portions, courses et traduction.
- **Déploiement** : commit + push sur `main` → Vercel déploie automatiquement.
- **Claude Code** (ingénieur principal) : implémente, corrige, déploie, audite le code.
- **ChatGPT** (architecte/produit) : lit ce fichier pour comprendre le contexte ; propose des améliorations UX/produit/design et des critiques d'architecture ; ne modifie pas le code directement — ses recommandations sont implémentées par Claude Code.
- **Après chaque grosse modification** : mettre à jour les sections 5, 6, 7 et la date en haut de ce fichier.
