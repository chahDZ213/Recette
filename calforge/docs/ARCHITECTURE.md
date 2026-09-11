# CalForge — Architecture

## Vue d'ensemble

CalForge est un **monolithe modulaire en couches strictes**. Une couche basse
n'importe jamais une couche haute ; l'interface graphique ne connaît que les
services et le bus d'événements.

```
┌─────────────────────────────────────────────────────┐
│  calforge.ui          PySide6 (docks, modèles Qt)   │
│    │ appels directs           ▲ événements (bridge) │
│    ▼                          │                     │
│  calforge.services    services applicatifs (DTOs)   │
│    │                          │                     │
│    ▼                          │                     │
│  calforge.analysis    diff, statistiques            │
│  calforge.formats     identification (plugins)      │
│    │                          │                     │
│    ▼                          │                     │
│  calforge.data        SQLAlchemy, Alembic, blobs    │
│─────────────────────────────────────────────────────│
│  calforge.core        config, logs, bus, DI, plugins│
└─────────────────────────────────────────────────────┘
```

La composition a lieu en un seul endroit : `calforge.app.ApplicationContext`
(racine de composition). Les tests et l'UI démarrent par le même chemin.

## Modules

| Module | Responsabilité | Remplaçable par |
|--------|----------------|-----------------|
| `core.config` | Configuration TOML validée (Pydantic), chemins applicatifs | — |
| `core.logging` | Journal fichier rotatif + console | — |
| `core.events` | Bus pub/sub thread-safe, événements typés | broker externe (post-v1) |
| `core.registry` | Conteneur de services typé (DI explicite) | framework DI |
| `core.plugins` | Découverte par entry points `calforge.plugins` | — |
| `data.database` | Moteur SQLite WAL, sessions, migrations, backups | PostgreSQL (voir ADR-0002) |
| `data.blobstore` | Binaires ECU adressés par contenu (SHA-256) | stockage objet (S3…) |
| `data.models` | Schéma ORM (jamais exposé hors de `services`) | — |
| `services.*` | Transactions, DTOs, publication d'événements | — |
| `analysis.diff` | Diff binaire vectorisé NumPy | — |
| `analysis.mapdetect` | Détection heuristique de cartographies | détecteurs tiers |
| `formats.*` | Identification de formats ECU (extensible) | plugins tiers |
| `packs` | Format ouvert de définitions (calforge-pack/1) | importeurs A2L/Damos |
| `ai.*` | Assistant : fournisseurs, contexte factuel (ADR-0009) | LLM local, autre vendeur |
| `labels` | Libellés FR partagés (feuille, sans Qt) | table i18n (v1.0) |
| `ui.*` | PySide6 ; parle uniquement aux services | autre frontend |

## Règles de conception non négociables

1. **Frontière ORM** : les modèles SQLAlchemy ne sortent jamais de la couche
   `services`. L'UI et les plugins reçoivent des DTOs Pydantic immuables.
2. **Faits vs hypothèses** (ADR-0004) : toute information affichée est soit
   prouvée depuis le contenu du fichier (`facts`), soit une hypothèse avec
   confiance ∈ [0, 1] **et** justification (`hypotheses`). Jamais de mélange.
3. **Immutabilité des originaux** : un binaire importé est stocké en lecture
   seule sous son SHA-256. Une modification est un *nouveau* blob.
4. **Threading** : les services sont thread-safe (session par appel). L'UI
   exécute les opérations lentes dans `QThreadPool` et revient sur le thread
   GUI par signaux Qt (connexions queued). Aucun verrou dans le code UI.
5. **Transactions courtes et explicites** : `Database.session()` est l'unique
   moyen d'accéder à la base (commit/rollback automatiques).
6. **Schéma** : toute évolution passe par une révision Alembic dans
   `data/migrations/versions`. Une révision appliquée n'est jamais modifiée.
7. **Extensibilité** : nouveau format ECU = un plugin (entry point), zéro
   modification du cœur. Les extensions internes utilisent le même mécanisme
   que les extensions tierces.

## Flux type : import d'un fichier ECU

1. L'UI (thread GUI) appelle `run_in_background(ecu_files.import_file, …)`.
2. Le worker hache et copie le fichier dans le blob store (atomique, dédupliqué).
3. Le pipeline d'identification exécute tous les `FormatIdentifier` et retient
   le rapport le plus spécifique (faits + hypothèses).
4. Le service persiste les métadonnées et publie `EcuFileImported`.
5. `EventBridge` re-émet l'événement en signal Qt → l'UI se rafraîchit sur le
   thread GUI.

## Décisions documentées

Les décisions structurantes sont dans `docs/adr/` (Architecture Decision
Records). Toute nouvelle décision importante doit y ajouter un ADR numéroté.
