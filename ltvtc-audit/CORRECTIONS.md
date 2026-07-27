# LTVTC Topo — corrections à appliquer

Audit du 26 juillet 2026. Sources : liste officielle des destinations PCTN
(*Taxi & VTC — 2026 → LTVTC topographie*, ge.ch/document/7124) et OpenStreetMap
(relevé du 2026-07-26) via l'API Overpass.

## Résumé

| Contrôle | Résultat |
|---|---|
| Réponses officielles « Où se trouve… » (133 fiches) | **133 conformes, 0 erreur** |
| Début/fin des 245 rues (490 points) | **480 exacts (98,0 %)**, 10 écarts |
| Rues du référentiel officiel manquantes | 3 |
| Fiche à renommer | 1 |

---

## 1. Rues officielles à ajouter (3)

| Question officielle | Réponse officielle | Page PDF |
|---|---|---|
| Chemin Michée-Chauderon | Au Petit-Saconnex | 30 |
| LA RUE MARIE THÉRESE MAURETTE | Près de la Route de Chêne | 30 |
| LA RUE PEARL-GROBET-SECRÉTAN | Près du Boulevard des Philosophes | 30 |

Les trois existent bien sur le terrain (vérifiées dans OSM).

## 2. Fiche à renommer (1)

`LA RUE CEARD` → **`LA RUE ROBERT-CEARD`**

La réponse (« Près de la rue du Rhône ») est correcte et ne change pas. Seul
l'intitulé doit reprendre la formulation officielle de l'examen. Il n'existe
qu'une seule voie, `Rue Robert-Céard` ; « Rue Céard » est la forme courte,
utilisée ailleurs dans le PDF officiel comme adresse.

## 3. Début/fin — erreurs de contenu confirmées (5)

La voie annoncée ne croise la rue concernée **nulle part** sur son parcours.

| Rue | Côté | Valeur actuelle | Valeur correcte |
|---|---|---|---|
| Avenue Appia | fin | Chemin des Crêts-de-Pregny | **Chemin des Geais** |
| Rue Boissonnas | début | Route des Jeunes | **Route des Acacias** |
| Chemin du Champ-Baron | début | Chemin des Genêts | **Chemin de la Rochette** |
| Route de Meyrin | début | Route Einstein | **Rue de la Servette** |
| Avenue des Tilleuls | début | Avenue De-Gallatin | **Voie couverte de Saint-Jean** |

## 4. Début/fin — croisement intermédiaire au lieu de l'extrémité (5)

La voie annoncée croise bien la rue, mais **en cours de parcours**, pas au bout.
Extrémités réelles calculées sur la géométrie OSM complète.

| Rue | Côté | Valeur actuelle | Extrémité réelle (OSM) |
|---|---|---|---|
| Rue du Grand-Pré | fin | Avenue Giuseppe-Motta | **Rue Chandieu** |
| Chemin Moïse-Duboule | fin | Rue de Moillebeau | **Chemin du Pommier** |
| Route de La-Capite | fin | Chemin du Pré-Langard | **Route de Thonon** (La Pallanterie) |
| Route de Jussy | fin | Chemin de la Forge | **Route de Monniaz / Route de Bellebouche** |
| Route de Chêne | fin | Chemin de Grange-Falquet | limite Chêne-Bougeries (non nommée dans OSM) |

> **À arbitrer avant correction.** Pour ces cinq cas, et en particulier
> `Route de Chêne`, l'étendue administrative officielle d'une rue genevoise peut
> différer du découpage OSM. `Chemin de Grange-Falquet` se situe près de la limite
> communale de Chêne-Bougeries : la valeur actuelle est peut-être correcte au sens
> du répertoire officiel des rues. À confronter au registre SITG avant de modifier.

## 5. Aucune correction nécessaire

Signalées à tort lors des passes intermédiaires, puis confirmées correctes avec
une tolérance de 80 m au lieu de 30 m (les grands carrefours genevois dépassent
30 m) : Rue Le-Corbusier (début et fin), Rue des Charmilles, Rue Lombard,
Route de Drize, Rue Blavignac, Rue de La-Tambourine, Rue François-Diday,
Rue Maurice-Barraud, Rue Caroline, Avenue de la Jonction, Rue Saint-Laurent,
Rue des Bossons, Avenue Louis-Casaï, Route d'Hermance, Route de Thonon.

## 6. Point pédagogique (hors correction)

Sur les 133 rues du référentiel officiel, le repère attendu à l'examen
(« près de X ») **n'est ni le début ni la fin** de la rue dans **31 cas**.
Un candidat qui n'a mémorisé que début/fin ne produira pas la réponse attendue
pour ces 31 rues. Il faut afficher en plus le repère officiel.

## Réserves de méthode

- OSM n'est pas le référentiel officiel du canton. Il fait foi sur la
  **connectivité** (quelle voie touche quelle voie), pas sur l'étendue
  administrative d'une rue.
- Les données début/fin ne figurent pas dans le document du PCTN : l'examen ne
  pose que des questions « Où se trouve : X ? ». Elles n'ont donc aucune source
  officielle à laquelle être confrontées.
- Les 112 rues « bonus » de l'app n'ont pas de réponse officielle et n'ont été
  contrôlées que sur leur début/fin.
