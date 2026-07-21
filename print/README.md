# Empreinte — impression 3D à la demande

App sœur de **mise.** dans ce dépôt, servie sous `/print/`. L'acheteur importe un
fichier **STL**, choisit les contraintes que sa pièce doit encaisser (humidité, UV,
température, résistance mécanique, flexibilité, contact alimentaire) ; l'app recommande
le **filament** et les **paramètres**, calcule les **grammes et le temps d'impression
exacts par vrai slicing (CuraEngine WASM)**, en déduit le **prix**, puis lance une
**commande Stripe** avec adresse de livraison et frais de port. Le créateur reçoit les
commandes payées dans un **espace créateur** avec un **bon de fabrication imprimable en PDF**.

## Pages
- `print/index.html` — application acheteur (upload, aperçu 3D, configurateur, prix, commande).
- `print/commandes.html` — espace créateur (liste des commandes payées + bon de fabrication PDF).
- `print/vendor/` — Three.js (aperçu) + cura-wasm & définitions (slicing), modules ES vendés.

## Backend (dossier `api/`)
- `api/pay/print-order.js` — crée la session Stripe Checkout à montant dynamique + livraison.
- `api/pay/print-orders.js` — liste les commandes payées pour le dashboard (protégé par token).
- `api/print-upload.js` — dépose le fichier STL dans Supabase Storage (bucket `print-files`).

## Variables d'environnement (Vercel)
Déjà présentes pour mise. et réutilisées : `STRIPE_SECRET_KEY` (sk_test_…),
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `PUBLIC_BASE_URL`.

À ajouter pour Empreinte :
- `EMPREINTE_ADMIN_TOKEN` — secret que tu choisis, demandé à l'entrée de l'espace créateur.

## Mise en ligne — checklist
1. **Supabase** : créer un bucket Storage **public** nommé `print-files` (stocke les STL commandés).
2. **Vercel** : définir `EMPREINTE_ADMIN_TOKEN` (Production).
3. Déployer (push sur `main`), puis :
   - acheteur : `/print/`
   - créateur : `/print/commandes.html` (saisir le token une fois).
4. Paiement en **mode test** (carte `4242 4242 4242 4242`). Passer en clés `live` Stripe
   quand tu veux encaisser réellement.

## Réglages créateur (dans l'app, ⚙︎ Réglages)
Catalogue de filaments (densité, €/g, €/min, vitesse, températures), marge & préparation,
seuil de livraison gratuite et forfait de livraison — le tout persistant et ajustable.

## Limites connues (MVP)
- Le prix est calculé côté client ; le montant Stripe est borné (1 €–20 000 €) mais non
  reslicé côté serveur. À durcir avant une vraie monétisation à fort volume.
- Upload STL limité à ~4,4 Mo (limite serverless Vercel). Au-delà : passer à un upload
  direct signé (Supabase `createSignedUploadURL`).
- L'espace créateur est protégé par un token partagé — suffisant en MVP, à migrer vers
  l'auth Supabase pour du multi-utilisateur.
