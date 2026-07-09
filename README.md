# mise. 🍳

> **La recette, sans le bouton pause.**

**mise.** est une Progressive Web App (PWA) qui transforme n'importe quelle source de recette — vidéo YouTube/Shorts, Instagram, TikTok, Facebook, site web (Marmiton, 750g, blogs…), photo ou texte libre — en une **fiche recette structurée et interactive**, utilisable les mains dans le pâton.

---

## ✨ Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| 🔗 **Extraction universelle** | Colle un lien YouTube, Instagram, TikTok, un lien Marmiton, une photo ou du texte brut — l'IA s'occupe du reste |
| ⚖️ **Portions ajustables** | Toutes les quantités se recalculent automatiquement (fractions ½ ¼ ¾ incluses) |
| 🍽️ **Mode « Sans balance »** | Conversions automatiques en cuillères/verres, activable d'un bouton |
| 👐 **Mode cuisson mains-libres** | Étapes plein écran, minuteurs intégrés, navigation vocale (*« suivant »*), lecture des étapes à voix haute, wake lock |
| 🔔 **Notifications push différées** | Alerte de fin de minuteur même application fermée (via QStash) |
| 📦 **Historique & collections** | Recettes sauvegardées par compte utilisateur (Supabase), favoris, listes de courses par catégorie et menu de la semaine |
| 🌍 **Bilingue FR / EN** | Interface et traduction des recettes à la volée |
| 🥦 **Idées depuis le frigo** | Photo ou liste d'ingrédients → Claude suggère des recettes |
| 📤 **Partage** | Lien public en lecture seule par recette |
| 📲 **Installable** | Fonctionne comme une application native (PWA installable sur iOS, Android, desktop) |

---

## 🏗️ Architecture

```
Utilisateur (PWA — index.html)
   │  colle un lien / photo / texte
   ▼
POST /api/extract ──────────────────────────────┐
   │                                             │
   ├─ URL vidéo  → Supadata (transcript)         │
   │              + YouTube Data API (description)│
   ├─ URL site   → fetch (schema.org + og:image) │
   ├─ Image      → Claude Vision                 │
   └─ Texte      → direct                        │
                                                 ▼
                              Claude (claude-sonnet-4-6)
                              → JSON { title, baseServings,
                                       ingredients[], steps[] }
                                                 │
   ┌─────────────────────────────────────────────┘
   ▼
Frontend : affichage recette → Supabase (historique + sauvegarde)
   │
   └─ Mode cuisson : minuteurs, voix, wake lock,
                     push différé (QStash → /api/send-push)
```

---

## 📁 Structure des fichiers

```
mise/
├─ index.html           ← TOUTE l'app frontend (HTML + CSS + JS vanilla, i18n FR/EN)
├─ sw.js                ← Service worker (cache network-first + réception push)
├─ manifest.json        ← Manifeste PWA
├─ icon-192.png / icon-512.png
├─ package.json         ← Seule dépendance : web-push
├─ api/
│  ├─ extract.js        ← Endpoint principal : extraction, vision, idées, traduction
│  ├─ schedule-push.js  ← Planifie un push différé via QStash
│  ├─ send-push.js      ← Appelé par QStash, envoie le push (protégé par SEND_SECRET)
│  └─ cancel-push.js    ← Annule un push planifié
├─ PROJECT_CONTEXT.md   ← Documentation de référence (architecture détaillée)
└─ README.md            ← ce fichier
```

---

## 🚀 Déploiement (Vercel — recommandé)

1. **Fork / clone** ce dépôt sur GitHub.
2. Sur [Vercel](https://vercel.com) : **New Project** → importe le dépôt.  
   Aucun framework à configurer : Vercel sert `index.html` en statique et détecte `api/*.js` comme fonctions serverless automatiquement.
3. Dans **Settings → Environment Variables**, ajoute :

| Variable | Obligatoire | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Clé API [console.anthropic.com](https://console.anthropic.com) |
| `SUPABASE_URL` | ✅ | URL de ton projet Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Clé service role Supabase |
| `VAPID_PUBLIC_KEY` | ✅ | Clé VAPID publique (notifications push) |
| `VAPID_PRIVATE_KEY` | ✅ | Clé VAPID privée |
| `SEND_SECRET` | ✅ | Secret partagé pour sécuriser `/api/send-push` |
| `QSTASH_URL` | ✅ | URL QStash (Upstash) pour les pushs différés |
| `QSTASH_TOKEN` | ✅ | Token QStash |
| `PUBLIC_BASE_URL` | ✅ | URL de production (ex. `https://mise.vercel.app`) |
| `YOUTUBE_API_KEY` | ⚙️ optionnel | YouTube Data API v3 (enrichit la description) |
| `PEXELS_API_KEY` | ⚙️ optionnel | Photo de plat de secours si aucune og:image |
| `ALLOWED_ORIGINS` | ⚙️ optionnel | Restreindre les origines autorisées à appeler l'API |
| `PREMIUM_CODES` | ⚙️ optionnel | Codes d'accès premium (séparés par des virgules) |

4. **Deploy** — les pushs sur `main` déclenchent un redéploiement automatique.

---

## 🛠️ Développement local

```bash
# 1. Installer les dépendances
npm install

# 2. Installer la CLI Vercel (si ce n'est pas déjà fait)
npm i -g vercel

# 3. Lier au projet Vercel (récupère les variables d'environnement)
vercel link

# 4. Lancer en local (frontend statique + fonctions serverless)
vercel dev
```

> ⚠️ Ouvrir `index.html` directement via `file://` ne fonctionnera pas (les appels à `/api/extract` échoueront). Utilise impérativement `vercel dev`.

---

## 🤝 Contribuer

Les contributions sont les bienvenues !

1. **Fork** le dépôt et crée une branche : `git checkout -b feature/ma-fonctionnalite`
2. Respecte les conventions du projet (voir `PROJECT_CONTEXT.md`) :
   - Code et commentaires en **français**
   - **Aucun framework, aucun build** — tout le frontend reste dans `index.html` en vanilla JS
   - Toute chaîne visible doit exister en FR **et** EN dans le dictionnaire `STR`
   - Ne jamais casser le format JSON des recettes (contrat central entre toutes les couches)
3. **Commit** avec un message clair : `git commit -m "feat: description courte"`
4. Ouvre une **Pull Request** vers `main` avec une description des changements.

---

## ⚠️ Limites connues

- **Transcripts YouTube depuis datacenter** : YouTube peut bloquer les IPs Vercel. Fallback proposé : coller la description manuellement, ou utiliser Supadata.
- **Vidéos sans sous-titres** : rien à extraire automatiquement — le mode texte libre prend le relais.
- **Instagram / TikTok / Facebook** : couverture via Supadata ; les vidéos sans légende ni sous-titres restent difficiles.
- **Traduction en masse** : ~5–10 s par recette ; avec 50 recettes, compter plusieurs minutes (toast de progression affiché).
- **Premium côté client uniquement** : le statut premium est actuellement stocké en `localStorage` — à migrer côté serveur avant toute monétisation sérieuse.

---

## 📄 Licence

Ce projet est sous licence **MIT**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

*Propulsé par [Claude (Anthropic)](https://anthropic.com) · [Supabase](https://supabase.com) · [Vercel](https://vercel.com) · [Supadata](https://supadata.ai)*
