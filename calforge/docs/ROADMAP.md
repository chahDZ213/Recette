# CalForge — Feuille de route

Règle : une version n'est ouverte que lorsque la précédente est stable
(tests verts, bugs corrigés, décisions documentées).

## ✅ v0.1 — Fondations (livrée)

- Noyau : config, logs, bus d'événements, DI, plugins, sauvegardes.
- Base SQLite WAL + migrations Alembic ; blob store SHA-256 immuable.
- Véhicules (CRUD + recherche instantanée), projets, import ECU dédupliqué.
- Identification de formats extensible (faits vs hypothèses).
- Diff binaire vectorisé ; UI sombre dockable ; vue hexadécimale ; tests.

## ✅ v0.2 — Dossier véhicule complet & bibliothèque (livrée)

- Pièces jointes véhicule : photos, documents, factures (blob store réutilisé,
  export à la demande, suppression sans destruction du contenu).
- Timeline unifiée : interventions, diagnostics, essais routiers, datalogs,
  étapes de calibration, notes (ADR-0006).
- Bibliothèque ECU globale : recherche instantanée (nom, SHA-256, format,
  véhicule, notes), versioning original → modifiés (fichier parent).
- Dossier véhicule en onglets : Fiche / Projets / Historique / Documents /
  Fichiers ECU ; création et édition de projets.
- Correctif majeur : livraison fiable des résultats des tâches d'arrière-plan
  sur le thread GUI (cycle de vie QRunnable), avec test de non-régression.

### Reporté en v0.3
- Onglets de projet multiples dans la zone centrale (sera plus pertinent
  combiné à la comparaison hexadécimale côte à côte).

## ✅ v0.3 — Analyse avancée (livrée)

- Comparaison hexadécimale côte à côte : défilement synchronisé, zones de
  différences surlignées, navigation zone par zone.
- Détection heuristique de cartographies (ADR-0007) : axe monotone + bloc à
  variation régulière, 8/16 bits LE/BE, **confiance plafonnée à 85 % +
  justification + validation/rejet humains persistants**.
- Annotations et favoris de navigation persistants sur plages d'octets,
  surlignés dans la vue hexadécimale, avec saut direct.
- Vue 2D des candidats (tableau à gradient thermique).
- Statistiques : entropie globale et par bloc, histogramme d'octets.
- Vue fichier unifiée : hexa + « Aller à l'offset » + annotations +
  candidats dans un onglet par fichier.

### Reporté
- Vue 3D (surface) : attend QtDataVisualization ou OpenGL custom, pertinent
  avec les fichiers de définition (v0.4) — décision documentée en ADR-0007.
- Onglets de projet multiples dans la zone centrale.

## v0.4 — Map Packs & définitions

- Modèle de définitions : plusieurs sources de définition par calculateur.
- Import de packs, organisation automatique, classement, historique.
- Association définitions ↔ fichiers par empreinte et signatures.

## v0.5 — Assistant IA

- Abstraction fournisseur (local/API) ; l'IA analyse, explique, résume,
  compare, propose — toujours avec confiance affichée et validation humaine.
- Recherche sémantique dans les notes, historiques et annotations.

## v0.6 — Rapports & exports

- Rapports PDF : dossier véhicule, comparaison, journal d'intervention.
- Exports (CSV/JSON) et modèles de rapport personnalisables.

## v1.0 — Produit

- Empaquetage Windows signé (installeur), mises à jour.
- Localisation complète (fr/en), thème clair, accessibilité.
- Durcissement performance : projets de centaines de milliers de fichiers
  (pagination des modèles Qt, index complémentaires, cache mémoire borné).

## Post-v1.0 (architecture déjà prête)

- API, synchronisation cloud, licences, multi-utilisateurs (la frontière
  services/DTOs et le bus d'événements sont conçus pour ce découplage).
