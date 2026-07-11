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
├── icons/ing/          ← pack d'icônes d'ingrédients (WebP 96px, ~3,5 Ko/icône)
│                          générées par ChatGPT (planches 3×3), découpées par icones-brutes/decoupe.py
│                          (dossier hors dépôt, dans Projet/) ; affichées via ingEmoji() avec repli emoji
├── PROJECT_CONTEXT.md  ← ce fichier
└── README.md
```

**Variables d'environnement Vercel :** `ANTHROPIC_API_KEY`, `SUPADATA_API_KEY`, `OPENAI_API_KEY` (photos IA), `IMAGE_MODEL` (défaut `gpt-image-2`), `IMAGE_QUALITY` (défaut `low`), `IMAGE_COMPRESSION` (défaut 55), `YOUTUBE_API_KEY` (opt.), `PREMIUM_CODES`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `SEND_SECRET`, `QSTASH_URL`, `QSTASH_TOKEN`, `PUBLIC_BASE_URL`, `ALLOWED_ORIGINS` (opt., protection API). `PEXELS_API_KEY` est obsolète (photos désormais générées par IA).

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
- ✅ Visuels d'ingrédients : **pack complet de 126 icônes personnalisées** (14 planches générées avec ChatGPT, style cohérent — légumes, fruits, viandes, poissons, crémerie, féculents, épicerie, condiments, légumineuses, boissons) couvrant la quasi-totalité des ingrédients détectés, repli emoji pour le reste, détection par mot entier avec règles de priorité (« semoule » ≠ « moule », « caramel au beurre salé » ≠ beurre…)
- ✅ Thème clair/sombre, notes personnelles, photos personnalisées, gating premium par codes
- ✅ Sécurité : contrôle d'origine API (opt-in `ALLOWED_ORIGINS`), limites de taille des entrées, filtrage des URLs `javascript:`, timeout réseau 75 s
- ✅ **Photos IA (2026-07-11)** : chaque recette reçoit une photo générée par `gpt-image-2` (endpoint `api/generate-image.js` — JWT Supabase obligatoire + contrôle d'origine, prompt construit sur titre + `imageQuery` + ingrédients, recompression WebP ~140 Ko via `output_compression`, upload Supabase Storage bucket public `recipe-images` chemin `gen/{user_id}/{recipeId}/{timestamp}.webp` avec le JWT utilisateur — policies : chacun n'écrit que dans son dossier). Déclenchement auto après les 5 flux d'import (asynchrone, badge « Photo en cours de génération… »), marqueur `imageSource` `user`/`ai`/`legacy` — **une photo perso n'est jamais écrasée**, régénération uniquement manuelle (menu ⋯). Backfill dans Réglages : confirmation obligatoire (nombre + coût), lots de 30, annulable, relançable. Les anciennes sources og:image/miniature YouTube/Pexels sont supprimées de `extract.js` (`imageQuery` conservé). Coût ≈ 0,006 $/image en `low`.
- ✅ **Galerie visuelle (2026-07-11)** : cartes photo 4:3 (photo en haut, titre 2 lignes dessous, ♥/🔖 en overlay, cuisson/partage/suppression discrets) via `recipeCard()` — page Recettes, collections, recherche, Récentes accueil. 1 colonne <560px, 2 colonnes ≥560px, 3 colonnes ≥1024px. Placeholder dégradé + couverts sans photo, badge de génération sur la carte, cartes accessibles clavier (Entrée/Espace, `alt` = titre).

## 6. Fonctionnalités en cours / récemment livrées

- 🔄 Traduction automatique globale au changement de langue — **livrée, à tester en production** (séquentielle, toast de progression `n/total`, persistée dans Supabase)
- 🔄 Animations de chargement rééquilibrées — livrées (messages 2,6 s, rattrapage accéléré quand le serveur a fini)
- ✅ Refonte UX — **fusionnée en production le 2026-07-11** : navigation persistante (tabbar mobile <1024px / barre supérieure ≥1024px — Accueil · Recettes · ＋Ajouter · Planning · Courses ; « ＋ » = action pure, jamais une destination), sheet « Ajouter une recette » regroupant les 4 méthodes (dialog accessible : focus piégé, Échap, overlay), accueil simplifié (hero court + recherche déléguée + CTA unique + Récentes), page Recettes dédiée (`#recipes`, onglets Enregistrées/Récentes, confirmation de suppression avec focus sur Annuler), libellés clarifiés FR/EN (« Importer la recette », « Scanner une recette », « Ajouter à une collection »…), bouton contextuel Enregistrer/Collection (fin de l'enregistrement implicite d'assignCollection), menu « ⋯ » sur la recette, mode cuisson amélioré (contenu remonté, « Étape X sur Y », minuteur actif proéminent, confirmation de sortie si minuteur), responsive desktop (accueil 720px, recettes 840px + 2 colonnes ≥768px, détail 720px ; courses/planning/cuisson inchangés), accessibilité (focus-visible, rôles status/alert, aria-labels FR/EN, contrastes mesurés et corrigés ≥4,5:1 dans les deux thèmes)

## 7. Problèmes et points faibles connus

1. **Premium contournable** : le statut est un simple `localStorage.mise_premium="1"`, vérifiable côté client uniquement. À migrer côté serveur (table Supabase + vérification dans `/api/extract`) avant toute monétisation sérieuse.
2. ~~RLS Supabase~~ ✅ vérifié (2026-07-11) : RLS actif sur `recipes` (4 policies `auth.uid() = user_id` : SELECT/INSERT/UPDATE/DELETE) et `shares` (lecture publique, création/suppression propriétaire).
3. ~~`ALLOWED_ORIGINS`~~ ✅ activé (2026-07-11) : `ALLOWED_ORIGINS=https://recette-xi.vercel.app` dans Vercel (Production). Testé : origine étrangère → 403, origine légitime → 200. Note : les requêtes sans header `Origin` (curl/scripts) passent — protection contre les sites tiers, pas contre les scripts directs (voir premium côté serveur).
4. **`index.html` monolithique (~2500 lignes)** : voulu (zéro build), mais la maintenabilité baisse à mesure que l'app grossit. Si le fichier dépasse ~4000 lignes, envisager un découpage.
5. **Traduction en masse séquentielle** : ~5-10 s par recette ; un utilisateur avec 50 recettes attendra plusieurs minutes (toast de progression, mais pas d'annulation).
6. **YouTube depuis datacenter** : certains transcripts échouent (blocage IP) → fallback « coller la description » proposé à l'utilisateur.
7. **Pas de tests automatisés** ni de CI.

## 8. Prochaines améliorations recommandées

1. Premium côté serveur (Supabase + vérification API).
2. Import/export des recettes (JSON, PDF).
3. Mode hors-ligne complet (recettes sauvées consultables sans réseau — le SW cache déjà les GET, mais les données viennent de Supabase).
4. Onboarding 3 écrans à la première ouverture.
5. Recherche par ingrédient dans ses recettes + filtre par temps de cuisson.
6. Tests E2E basiques (Playwright) sur les parcours critiques : extraction, portions, mode cuisson.

---

## Conventions pour les assistants IA

- **Langue du code et des commentaires : français.** Interface bilingue FR/EN via le dictionnaire `STR` dans `index.html` (toute nouvelle chaîne visible doit exister en FR **et** EN, et être branchée dans `applyLang()`).
- **Aucun framework, aucun build** : tout changement frontend se fait dans `index.html` en vanilla JS. Échapper toute donnée utilisateur avec `esc()` avant `innerHTML`.
- **Ne jamais casser le format recette** (section 3) : c'est le contrat entre extraction, affichage, portions, courses et traduction.
- **Déploiement** : commit + push sur `main` → Vercel déploie automatiquement.
- **Claude Code** (ingénieur principal) : implémente, corrige, déploie, audite le code.
- **ChatGPT** (architecte/produit) : lit ce fichier pour comprendre le contexte ; propose des améliorations UX/produit/design et des critiques d'architecture ; ne modifie pas le code directement — ses recommandations sont implémentées par Claude Code.
- **Après chaque grosse modification** : mettre à jour les sections 5, 6, 7 et la date en haut de ce fichier.
