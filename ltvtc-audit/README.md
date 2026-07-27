# Audit LTVTC — Topographie ville et canton

Vérification du contenu de l'application **ltvtc-topo** (`ltvtc-topo.vercel.app`),
PWA de préparation à l'examen LTVTC de Genève.

> L'application n'est reliée à aucun dépôt Git : elle a été déployée directement
> sur Vercel. Le code source React n'a pas pu être récupéré (page source Vercel
> protégée par authentification). Les données ci-dessous ont été **extraites du
> bundle JavaScript compilé** servi en production.

## Sources de vérification

| Source | Usage |
|---|---|
| Liste officielle des destinations PCTN — *Taxi & VTC 2026 → LTVTC topographie* ([ge.ch/document/7124](https://www.ge.ch/document/7124/telecharger)) | Référentiel des questions « Où se trouve : X ? » |
| *Examens LTVTC — Exemple de questions*, Commission d'examens LRDBHD ([ge.ch/document/39903](https://www.ge.ch/document/39903/telecharger)) | Confirme le type de question « Indiquez où débute et se termine » |
| OpenStreetMap via l'API Overpass (relevé du 2026-07-26) | Connectivité réelle des voies (début/fin) |

## Résultats

| Contrôle | Résultat |
|---|---|
| Réponses officielles « Où se trouve… » (133 fiches) | **133 conformes, 0 erreur** |
| Début/fin des 245 rues (490 points contrôlés) | **480 exacts — 98,0 %** |
| Rues du référentiel officiel manquantes | 3 (ajoutées) |
| Fiche à renommer | 1 (`LA RUE CEARD` → `LA RUE ROBERT-CEARD`) |

Détail complet dans [`CORRECTIONS.md`](CORRECTIONS.md) et
[`AUDIT_TOPOGRAPHIE.md`](AUDIT_TOPOGRAPHIE.md).

## Fichiers

| Fichier | Contenu |
|---|---|
| `data/dataset_full.json` | Données extraites du bundle en production — **245 fiches**, géométrie comprise |
| `data/dataset_corrige.json` | Idem, **corrections appliquées** — 248 fiches, prêt à intégrer |
| `data/officiel.json` | Référentiel officiel PCTN complet — 1030 destinations, 50 catégories |
| `data/verified.json` | Contrôle OSM point par point des 490 début/fin |
| `data/croisements.json` | Voies croisant réellement chaque rue litigieuse |
| `data/extremites2.json` | Extrémités géométriques réelles calculées sur OSM |
| `data/final80.json` | Recontrôle des écarts avec tolérance de 80 m |
| `data/nouvelles.json` | Les 3 rues officielles ajoutées, géométrie OSM comprise |

## Scripts

`verify2.py` (début/fin des 245 rues) · `verify3.py` (croisements réels) ·
`verify5.py` (extrémités géométriques) · `final.py` (recontrôle à 80 m) ·
`build_corrige.py` (application des corrections)

## Réserves

- **OSM n'est pas le référentiel officiel du canton.** Il fait foi sur la
  connectivité des voies, pas sur l'étendue administrative d'une rue.
- **Le format début/fin est bien un type de question officiel** (épreuve 2 :
  « INDIQUEZ OÙ DÉBUTE ET SE TERMINE » — voir
  [ge.ch/document/39903](https://www.ge.ch/document/39903/telecharger)). En
  revanche le PCTN ne publie pas les réponses de ce type : elles ont été
  vérifiées contre OpenStreetMap, pas contre un référentiel cantonal.
- **Une tolérance de 30 m produit des faux positifs** : les grands carrefours
  genevois la dépassent. Tous les contrôles ont été refaits à 80 m.
- Les **112 rues hors référentiel officiel** n'ont été contrôlées que sur leur
  début/fin, faute de réponse officielle à laquelle les confronter.
