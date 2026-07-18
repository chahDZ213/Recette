# CalForge — Feuille de route

Règle : une version n'est ouverte que lorsque la précédente est stable
(tests verts, bugs corrigés, décisions documentées).

## ✅ v0.1 — Fondations (livrée)

- Noyau : config, logs, bus d'événements, DI, plugins, sauvegardes.
- Base SQLite WAL + migrations Alembic ; blob store SHA-256 immuable.
- Véhicules (CRUD + recherche instantanée), projets, import ECU dédupliqué.
- Identification de formats extensible (faits vs hypothèses).
- Diff binaire vectorisé ; UI sombre dockable ; vue hexadécimale ; tests.

## v0.2 — Dossier véhicule complet & bibliothèque de fichiers

- Pièces jointes véhicule : photos, documents, factures (blob store réutilisé).
- Historiques : interventions, diagnostics, essais routiers, logs (timeline).
- Bibliothèque ECU globale : recherche par empreinte/nom/format, versioning
  original → modifiés, commentaires.
- Gestion multi-projets simultanés dans l'UI (onglets de projet).
- Éditeur de fiche projet enrichi (statuts, jalons, échéances).

## v0.3 — Analyse avancée

- Vue de comparaison hexadécimale côte à côte avec surlignage des zones.
- Détection heuristique de zones « cartographies » (axes monotones, gradients)
  avec **score de confiance + justification + validation manuelle**.
- Annotations persistantes sur offsets/plages ; favoris de navigation.
- Vues 2D (tableau) et 3D (surface) des zones validées.
- Statistiques de fichier (entropie par bloc, histogrammes).

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
