# CalForge

**Assistant professionnel de calibration ECU assisté par intelligence artificielle.**

CalForge centralise tout le travail d'un calibrateur : véhicules, projets, fichiers ECU,
comparaisons, historiques et documentation — avec une règle absolue : *aucune donnée
inventée*. Tout ce que le logiciel affiche est soit un **fait mesuré**, soit une
**hypothèse** accompagnée de son niveau de confiance et de sa justification.

## État actuel — Version 0.1 (fondations)

- Noyau applicatif modulaire : configuration validée, journalisation complète,
  bus d'événements, registre de services, système de plugins (entry points).
- Base SQLite (WAL) migrée par Alembic, sauvegardes automatiques horodatées.
- Gestion des véhicules (fiche, recherche instantanée multi-champs) et des projets.
- Import de fichiers ECU : stockage adressé par contenu (SHA-256, dédupliqué,
  binaires immuables), identification de format extensible par plugins.
- Moteur de comparaison binaire vectorisé (NumPy) avec zones de différences.
- Interface sombre PySide6 : docks déplaçables, onglets, vue hexadécimale,
  glisser-déposer, raccourcis clavier, journal intégré, imports multithreadés.
- 33 tests automatiques (services, base, blobs, diff, formats, UI offscreen).

Voir [docs/ROADMAP.md](docs/ROADMAP.md) pour les versions suivantes et
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pour la conception détaillée.

## Installation (développement)

```bash
cd calforge
python3.13 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Lancer l'application

```bash
.venv/bin/python -m calforge
```

## Tests et qualité

```bash
.venv/bin/python -m pytest tests/
.venv/bin/ruff check src tests
```

## Raccourcis clavier

| Raccourci | Action |
|-----------|--------|
| `Ctrl+N`  | Nouveau véhicule |
| `F2`      | Modifier le véhicule sélectionné |
| `Ctrl+I`  | Importer des fichiers ECU |
| `Ctrl+F`  | Recherche instantanée |
| `Ctrl+Q`  | Quitter |

## Où sont mes données ?

- **Données** (base + binaires + sauvegardes) : répertoire utilisateur standard
  (`%LOCALAPPDATA%\CalForge` sous Windows, `~/.local/share/CalForge` sous Linux).
- **Configuration** : `calforge.toml` dans le répertoire de configuration utilisateur.
- **Journaux** : répertoire de logs utilisateur, rotation automatique.

Les binaires ECU importés sont stockés en lecture seule et vérifiés par empreinte
SHA-256 : un original ne peut jamais être altéré silencieusement.
