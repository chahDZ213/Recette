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

## ✅ v0.4 — Map Packs & définitions (livrée)

- Format ouvert « calforge-pack/1 » (JSON versionné, ADR-0008) : import et
  export sans perte, éditable à la main.
- Sources multiples par calculateur, chacune avec ses critères de
  correspondance : SHA-256 exact, signature d'octets, taille.
- Application au magasin de candidats : confiance dérivée de la force de la
  correspondance (0,95 / 0,85 / 0,60), justification nommant le pack,
  validation humaine conservée, décisions humaines jamais écrasées.
- Conversion physique (facteur/offset/unité) affichée dans la vue 2D,
  valeurs brutes en infobulle.
- Onglet « Map Packs » (Ctrl+M) : sources, cartographies définies,
  import/export/suppression.

### Reporté
- Importeurs Damos/A2L/ECM → traduits vers le modèle calforge-pack.

## ✅ v0.5 — Assistant IA (livrée)

- Abstraction de fournisseur (ADR-0009) : analyste hors-ligne déterministe par
  défaut (zéro config, zéro réseau) + fournisseur Claude optionnel (SDK
  officiel, activé par clé API).
- Frontière de contexte factuel : l'IA ne reçoit que faits mesurés et
  hypothèses déjà scorées ; jamais de fichier brut ni d'accès aux services.
- Opérations : résumé de fichier/véhicule, propositions de pistes, question
  libre ; chaque réponse affiche fournisseur, faits utilisés, hypothèses,
  confiance et avertissement, et est enregistrable dans l'historique.
- Contrat d'honnêteté imposé dans le prompt système du fournisseur Claude.
- Dock « Assistant IA » (Ctrl+J) contextuel (véhicule / fichier actif).

### Reporté
- Recherche sémantique (embeddings) dans notes/historiques/annotations →
  candidate pour une v0.6+ une fois un fournisseur d'embeddings abstrait.

## ✅ v0.6 — Rapports & exports (livrée)

- Rapports HTML/PDF : dossier véhicule complet, comparaison de fichiers
  (ADR-0010) — source unique HTML, PDF rendu par Qt sans dépendance ajoutée.
- Les rapports listent les cartographies validées (faits) et signalent les
  zones de différences recoupant des cartographies connues ; avertissement
  d'honnêteté systématique.
- Exports CSV (fichiers) et JSON (dossier véhicule structuré).
- Lancement en une commande (`run.sh` / `run.bat`) et données de démonstration
  pré-remplies (`--seed-demo`, idempotent) pour un premier essai immédiat.

### Reporté
- Modèles de rapport personnalisables et graphiques (nécessitent un second
  moteur de rendu au-delà du sous-ensemble Qt rich text).

## ✅ v0.7 — Import universel & éditeur de cartographie (livrée)

- Import universel (ADR-0011) : tout fichier accepté, sélecteur par défaut
  « Tous les fichiers », aucune restriction par extension/format/taille.
- Éditeur 2D : édition directe des cellules + outil « +X % » (sélection ou
  carte entière), enregistrement en nouveau fichier dérivé ; original
  préservé octet par octet (encode_block non destructif, ADR-0003).
- Export d'un fichier ECU sur le disque (nom/extension libres).
- Détecteur : recherche web des techniques réelles (axe monotone + table
  lisse, comparaison ori/modifié) intégrée à la stratégie.

### Reporté (v0.8+)
- Détection de blocs lisses sans axe explicite ; détection de maps par
  comparaison ori↔modifié promue en candidats ; édition 3D.

## v1.0 — Produit

- Empaquetage Windows signé (installeur), mises à jour.
- Localisation complète (fr/en), thème clair, accessibilité.
- Durcissement performance : projets de centaines de milliers de fichiers
  (pagination des modèles Qt, index complémentaires, cache mémoire borné).

## Post-v1.0 (architecture déjà prête)

- API, synchronisation cloud, licences, multi-utilisateurs (la frontière
  services/DTOs et le bus d'événements sont conçus pour ce découplage).
