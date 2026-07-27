# LTVTC Topo

PWA de préparation à l'examen LTVTC de Genève — **Topographie Ville et Canton**.

Source reconstruite à partir du déploiement `ltvtc-topo.vercel.app`, dont le code
n'avait jamais été versionné. Les données ont été auditées puis corrigées : voir
[`../ltvtc-audit/CORRECTIONS.md`](../ltvtc-audit/CORRECTIONS.md).

## Ce que couvre l'application

L'épreuve de topographie comporte deux types de questions officiels :

| Question officielle | Champ | Fiches |
|---|---|---|
| « Où se trouve : X ? » | `referenceOfficial` | 136 |
| « Indiquez où débute et se termine » | `beginStreet` / `endStreet` | 248 |

Le mode examen reproduit le format officiel : **6 propositions**, deux à choisir.

## Démarrer

```sh
npm install
npm run dev      # développement
npm run build    # production (typecheck + build)
npm run preview  # servir le build
```

## Structure

```
src/
  data/streets.json   248 rues : géométrie, début/fin, repère officiel, distracteurs
  data/streets.ts     typage et sélecteurs
  lib/quiz.ts         tirage pondéré, composition des questions, correction
  lib/progress.ts     progression Leitner (IndexedDB) et liste des rues révisées
  lib/speech.ts       lecture vocale
  components/         carte Leaflet
  screens/            accueil, révision, examen
```

## Qualité des données

- Les 136 réponses « Où se trouve » sont **identiques au document officiel du PCTN**
  ([ge.ch/document/7124](https://www.ge.ch/document/7124/telecharger)), au caractère près.
- Les couples début/fin sont vérifiés contre OpenStreetMap : **480 points exacts sur 490**.
- Le PCTN ne publie pas de corrigé pour les questions début/fin ; OpenStreetMap fait
  autorité sur la connectivité des voies, pas sur l'étendue administrative d'une rue.

## Réponses multiples

À certains carrefours, plusieurs voies aboutissent au même bout de rue.
`beginAlternatives` / `endAlternatives` listent les réponses également acceptées ;
la première entrée est toujours la réponse principale. La correction les accepte
toutes, et aucune d'elles n'est utilisée comme distracteur.
