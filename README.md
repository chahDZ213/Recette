# mise.

Colle un lien YouTube → recette interactive (portions ajustables + mode cuisson).

## Structure

```
mise/
├── index.html          # le front (statique)
├── api/extract.js      # backend serverless : transcript + description → Claude → JSON
└── package.json
```

## Déploiement Vercel

1. Mets ce dossier sur un repo GitHub.
2. Sur Vercel : "New Project" → importe le repo. Aucun framework, Vercel sert `index.html` en statique et `api/extract.js` comme fonction serverless automatiquement.
3. Dans Settings → Environment Variables, ajoute :
   - `ANTHROPIC_API_KEY` (obligatoire) — ta clé console.anthropic.com
   - `YOUTUBE_API_KEY` (optionnel mais recommandé) — clé YouTube Data API v3, pour récupérer la description en plus des sous-titres
4. Deploy.

En local pour tester : `npm i -g vercel` puis `vercel dev` (le front seul ouvert en `file://` ne pourra pas appeler le backend).

## Comment ça marche

`api/extract.js` reçoit `{ url }`, récupère **les sous-titres** (youtube-transcript) **et la description** (YouTube Data API), assemble le tout et l'envoie à Claude qui renvoie un JSON structuré `{ title, baseServings, ingredients[], steps[] }`. Le front fait le scaling des portions et le mode cuisson côté navigateur.

## Limites à connaître (honnête)

- **youtube-transcript depuis Vercel** : YouTube bloque parfois les IP datacenter. Si tu vois beaucoup d'échecs de transcript en prod, les options solides sont : un service de transcript dédié (ex. Supadata), `youtubei.js` avec cookies, ou un proxy résidentiel. La description via YouTube Data API, elle, reste fiable.
- **Vidéos sans sous-titres ni recette écrite** : il n'y a alors rien à extraire automatiquement → le repli "coller la description à la main" prend le relais.
- **Instagram / TikTok / Facebook** : pas couverts ici. Ça nécessite soit la caption (scraping), soit un speech-to-text sur l'audio (Whisper). À faire dans un second temps une fois YouTube validé.
