# Plan — Photos IA + galerie visuelle pour mise. (2026-07-11, v2 — révisé après retour Codex)

> Statut : PLAN UNIQUEMENT — aucune implémentation avant le « go » explicite de l'utilisateur.
> v2 : modèle gpt-image-2, galerie 1 colonne mobile, hiérarchie imageSource explicite, règles Storage précisées, backfill durci.

## Constat sur l'existant (vérifié dans le code)

- Images actuelles : URLs externes (og:image, miniature YouTube `img.youtube.com/vi/{id}/hqdefault.jpg`, Pexels via `PEXELS_API_KEY`) ou data-URL base64 (photos perso compressées client, `fileToCompressed`) stockées dans le JSONB `recipes.data`. Pas de Supabase Storage aujourd'hui.
- L'extraction génère déjà `imageQuery` (2-4 mots anglais décrivant le plat) → réutilisable pour le prompt IA.
- Listes : lignes compactes (`sr-thumb` à gauche, titre, bouton cuisson) rendues par `renderList()` (~index.html:2178) et la recherche accueil (~1334).
- Schéma Supabase `recipes` : id, user_id, data (jsonb), fav, saved, created_at. RLS OK (auth.uid()=user_id).

## PARTIE 1 — Génération de photos IA

### Architecture
- Nouvel endpoint serverless `api/generate-image.js` :
  - Entrée `{ recipeId, title, imageQuery, ingredients[3-5] }` + header `Authorization: Bearer <JWT Supabase>`.
  - Prompt : « Professional food photography of {title} ({imageQuery}), featuring {ingredients}, natural light, appetizing plating, realistic, shallow depth of field » (pas de texte/mains dans l'image).
  - OpenAI Images **`gpt-image-2`** (modèle actuel, sorti 2026-04). Modèle et qualité **configurables par variables d'env serveur, sans toucher au code** : `IMAGE_MODEL=gpt-image-2` (défaut) et `IMAGE_QUALITY=low|medium` (défaut `low` pour démarrer, montée en `medium` possible à tout moment via Vercel + redeploy). Taille 1024×1024, sortie WebP.
  - Upload Supabase Storage, bucket public `recipe-images`, chemin **unique et versionné** `gen/{user_id}/{recipeId}/{timestamp}.webp` — jamais d'écrasement de fichier ; une régénération crée un nouveau fichier et l'ancien est supprimé après succès (l'URL dans `recipe.data` bascule atomiquement, pas de cache stale).
  - Réponse : URL publique. Le front écrit `recipe.image = url` + `recipe.imageSource = "ai"` et persiste via `persistRecipeChange()` existant.
- Pourquoi Storage et pas base64 JSONB : ~100-200 Ko/image ; en base64, `loadRecipesFromDB()` téléchargerait des Mo pour la liste. Storage = URL légère, CDN, cache SW, JSONB petit. Photos perso restent en base64 (inchangé).
- Env Vercel (serveur uniquement) : `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `IMAGE_MODEL`, `IMAGE_QUALITY`. Jamais de clé dans le front.

### Déclenchement (nouvelles recettes : lien, création IA, collage texte)
1. Flux d'extraction inchangé, n'attend PAS l'image.
2. Recette affichée immédiatement avec placeholder.
3. Appel asynchrone `/api/generate-image` (~5-20 s) → fondu à l'arrivée + persistance.
4. Échec → placeholder conservé + « Générer la photo » dans le menu ⋯ de la fiche.

### Classification des images (`recipe.imageSource`) et anti-régénération
Trois provenances, marquées explicitement dans le JSONB :
- **`"user"`** : photo ajoutée manuellement (aujourd'hui : data-URL base64). **Intouchable** — jamais remplacée par l'IA, ni à l'import ni au backfill. Seul l'utilisateur peut la supprimer/changer.
- **`"ai"`** : photo générée (URL Supabase Storage). Considérée définitive ; régénération uniquement sur action manuelle explicite.
- **`"legacy"` (ou champ absent)** : ancienne image externe YouTube/Pexels/og:image, ou pas d'image. Éligible au backfill.
Détection rétroactive des recettes existantes (qui n'ont pas le marqueur) : data-URL base64 → `"user"` ; URL du bucket `recipe-images` → `"ai"` ; toute autre URL http(s) ou absence d'image → `"legacy"`. Le marqueur est posé au premier passage pour ne pas re-détecter à chaque fois.
Anti-régénération : URL persistée + marqueur → plus jamais de génération à l'ouverture ; génération auto seulement quand `imageSource` vaut `"legacy"`/absent au moment d'un import ou du backfill.

### Backfill (recettes existantes) — prudent par conception
- **Jamais automatique** : bouton dans Réglages « Générer les photos manquantes (n) » → dialogue de confirmation affichant le nombre de recettes concernées et une estimation de coût, avant tout appel.
- Par lots : plafond par lancement (proposé : 30), séquentiel, toast n/total, bouton Annuler à tout moment.
- Relançable : skip automatique de tout ce qui est `imageSource: "ai"` ou `"user"` → une relance reprend uniquement le reste.
- Cibles strictes : uniquement `imageSource: "legacy"`/absent (pas de photo IA valide, pas de photo manuelle).
- Côté serveur : le backfill passe par le même endpoint `/api/generate-image` protégé (JWT Supabase obligatoire + ALLOWED_ORIGINS + plafond de fréquence par utilisateur) — aucun endpoint « batch » ouvert, aucune génération possible sans session authentifiée.

### Retrait de l'ancienne extraction d'image (`api/extract.js`)
- Supprimer : `pexelsPhoto()`, récupération og:image, miniature YouTube comme `recipe.image`.
- Garder : `imageQuery`, extraction titre/ingrédients/étapes, vision (photo de recette), photo de frigo.
- `PEXELS_API_KEY` obsolète (retirer de Vercel + doc).

### Erreurs / limites / coûts
- OpenAI erreur/quota : 1 retry backoff serveur, puis erreur propre ; front garde le placeholder + retry manuel.
- Timeout serveur ~60 s ; UI jamais bloquée.
- Abus : ALLOWED_ORIGINS (déjà actif) + vérification JWT Supabase côté serveur (seuls les connectés génèrent ; user_id fiable pour le chemin Storage). Option : compteur/jour par user.
- Coût : ordre de grandeur attendu de quelques centimes par image (à confirmer sur la page pricing OpenAI pour gpt-image-2 au moment de l'implémentation — le test « 3 recettes » sert aussi à mesurer le coût réel avant d'ouvrir le backfill). Backfill 100 recettes : estimation affichée dans le dialogue de confirmation.

### Sécurité / règles de stockage
- Bucket public `recipe-images` : **réservé aux images IA générées**, rien d'autre n'y transite. Lecture publique (URLs non devinables : UUID recette + timestamp), écriture serveur uniquement (service role), aucune policy d'écriture client.
- **Pas de base64 lourd dans `recipe.data.image`** pour les images IA : uniquement l'URL Storage. (Les photos perso restent en base64 comme aujourd'hui — comportement inchangé ; si un jour on les migre vers Storage, ce sera un **bucket privé** avec URLs signées, hors périmètre de ce chantier.)
- RLS `recipes` inchangées.

## PARTIE 2 — Galerie visuelle

### Où
- Un composant « carte recette » unique : page Recettes (Enregistrées/Récentes), filtres collections, recherche, section Récentes de l'accueil.
- Listes utilitaires (menu semaine, courses) restent compactes.

### Grille — grandes photos d'abord
- Image 4:3 (`aspect-ratio` + `object-fit:cover`).
- **Petits mobiles (<480px) : 1 colonne** — carte pleine largeur (~340px de photo), effet « magazine culinaire ».
- **Grands mobiles / petites tablettes : 2 colonnes seulement quand l'écran permet vraiment une belle image** (seuil relevé à ~560px plutôt que 480 — priorité confirmée : moins de cartes mais plus appétissantes).
- **Tablette (768-1023px) : 2-3 colonnes** selon largeur (breakpoint intermédiaire ~900px).
- **Desktop (≥1024px) : 3 colonnes** dans le conteneur 840px existant (~265px/photo — grandes et appétissantes) ; 4 colonnes seulement si on élargit le conteneur (option, à voir en test visuel).
- Principe directeur : photo jamais sous ~160px de large ; en cas de doute, moins de colonnes.

### Carte
- Photo en haut, badge favori ♥ en overlay (coin sup. droit), titre 2 lignes max sous la photo + méta discrète.
- Carte entière = ouvrir la recette ; ♥ = toggle direct ; autres actions (cuisson, supprimer, collection) dans la fiche recette (recommandation à valider — alternative : bouton cuisson sur la carte).
- Accessibilité : carte bouton/lien nommée par le titre, `alt` = titre, ♥ `aria-pressed`, focus-visible, ordre de tabulation naturel.

### États
- Génération en cours : dégradé (--cream/accent) + icône assiette + shimmer, titre visible, carte cliquable.
- Échec : même placeholder sans spinner, régénération depuis la fiche.
- Perf : `loading="lazy"`, `aspect-ratio` (zéro layout shift), 1 seule taille d'image (1024 WebP). Plus tard si besoin : transformations d'image Supabase pour miniatures.

## Fichiers modifiés
- `api/generate-image.js` (nouveau)
- `api/extract.js` (retrait sources d'image, garde imageQuery)
- `index.html` (CSS grille/cartes, renderList(), déclenchement post-import, placeholder+retry, backfill Réglages, i18n FR/EN, applyHeroPhoto compat)
- `sw.js` (bump cache)
- Supabase : bucket `recipe-images`
- Vercel : +`OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `IMAGE_MODEL=gpt-image-2`, `IMAGE_QUALITY=low` ; −`PEXELS_API_KEY`
- `PROJECT_CONTEXT.md`, `README.md`

## Risques
1. Coût si endpoint abusé (mitigé JWT + origine + plafonds).
2. Latence génération 5-20 s (design placeholder-first).
3. Photo IA = plat type, pas le plat exact de la vidéo (assumé).
4. index.html grossit (~2600 lignes, seuil de découpage ~4000 en vue).
5. Mode partage public : vérifier le rendu des URLs Storage.
6. Cohabitation vieilles images externes / images IA jusqu'à la fin du backfill.

## Tests
1. Endpoint seul (curl) : génération, upload, URL publique, 401 sans JWT, 403 origine étrangère.
2. 3 flux d'import : placeholder immédiat → photo ~15 s → persistée (reload = pas de régénération).
3. Échec simulé (clé invalide) : placeholder + retry manuel.
4. Backfill : mélange photos perso / YouTube / sans image → bonnes cibles seulement, annulation, relance reprend.
5. Photo perso jamais écrasée ; suppression → régénération possible.
6. Grille : 375px (1 col), 600px (2 col), 900px (2-3 col), 1280px (3 col), clair/sombre, clavier, lecteur d'écran.
6bis. Vérifier la hiérarchie imageSource : photo perso posée puis backfill lancé → la perso survit ; recette YouTube → remplacée ; recette IA → skippée.
7. Mode public/partage.
8. Mesurer le coût réel sur 5 générations avant d'ouvrir le backfill.

## Décisions actées (retours Codex + utilisateur)
- Modèle/qualité pilotés par env : `IMAGE_MODEL=gpt-image-2`, `IMAGE_QUALITY=low` au départ, montée en `medium` sans changer le code.
- Galerie : priorité aux grandes images — 1 colonne petits mobiles, 2 colonnes seulement à partir de ~560px, moins de cartes mais plus appétissantes.

## Questions ouvertes
- Après le test 3 recettes en `low` : rester en `low` ou passer `medium` ?
- Actions sur carte : épurée (ouvrir + ♥) ou garder le bouton cuisson par carte ?
- Backfill : plafond 30 OK ? Confirmé : cibles = uniquement `imageSource legacy/absent` (les YouTube/Pexels existantes sont remplacées, les photos perso jamais).
- Desktop : rester à 3 colonnes dans le conteneur 840px, ou élargir le conteneur pour 4 colonnes ?
