# CalForge

**Assistant professionnel de calibration ECU assisté par intelligence artificielle.**

CalForge centralise tout le travail d'un calibrateur : véhicules, projets, fichiers ECU,
comparaisons, historiques et documentation — avec une règle absolue : *aucune donnée
inventée*. Tout ce que le logiciel affiche est soit un **fait mesuré**, soit une
**hypothèse** accompagnée de son niveau de confiance et de sa justification.

## État actuel — Version 0.7 (import universel & éditeur de cartographie)

Nouveautés v0.7 (ADR-0011) :

- **Import universel** : *tout* fichier est accepté — `.ori`, `.bin`, dumps
  complets BDM/boot et des dizaines d'extensions ECU. Le sélecteur s'ouvre
  sur « Tous les fichiers » ; aucun format, aucune marque, aucune année n'est
  jamais refusé.
- **Éditeur de cartographie 2D** : modifiez les cellules directement ou
  appliquez un **+X %** à une sélection ou à toute la carte, puis enregistrez
  comme **nouveau fichier**. L'original reste **intact octet par octet** —
  une modification est toujours un fichier dérivé traçable.
- **Export sur disque** : enregistrez n'importe quel fichier (modifié ou non)
  sous le nom/extension de votre choix.

Nouveautés v0.6 :

- **Rapports HTML/PDF** : dossier véhicule complet et comparaison de fichiers,
  générés depuis une source HTML unique et rendus en PDF par Qt (sans
  dépendance ajoutée, ADR-0010).
- Les rapports listent les **cartographies validées** et signalent les zones
  de différences touchant des cartographies connues.
- **Exports CSV** (fichiers) et **JSON** (dossier véhicule structuré).
- **Lancement en une commande** (`run.sh` / `run.bat`) et **données de
  démonstration** pré-remplies pour un premier essai immédiat.

Acquis v0.5 :

- **Assistant IA** (Ctrl+J) contextuel : résume un fichier ou un véhicule,
  propose des pistes, répond aux questions — en ne s'appuyant que sur des
  **faits mesurés** et des **hypothèses déjà scorées**, jamais sur le fichier
  brut (ADR-0009).
- **Deux fournisseurs interchangeables** : un analyste **hors-ligne**
  déterministe par défaut (aucune configuration, aucun réseau, aucune clé) et
  un fournisseur **Claude** optionnel (SDK officiel, activé par clé API).
- Chaque réponse affiche son fournisseur, les faits utilisés, les hypothèses,
  et un avertissement ; elle est enregistrable dans l'historique du véhicule.
- L'assistant n'invente jamais de donnée : le contrat faits/hypothèses est
  imposé jusque dans le prompt système du fournisseur IA.

Configuration de l'IA (optionnelle) : renseignez `ANTHROPIC_API_KEY` dans
l'environnement, ou `[ai] provider = "anthropic"` dans `calforge.toml`. Sans
clé, l'analyste hors-ligne est utilisé.

Acquis v0.4 :

- **Map Packs** (Ctrl+M) : format ouvert `calforge-pack/1` (JSON), import et
  export sans perte, plusieurs sources de définitions par calculateur.
- **Correspondance automatique** définitions ↔ fichiers : empreinte SHA-256
  exacte, signature d'octets ou taille — la confiance des cartographies
  proposées reflète la force de la correspondance (ADR-0008).
- **Conversion physique** dans la vue 2D : `physique = brut × facteur +
  offset`, unité affichée, valeurs brutes en infobulle.
- Les décisions humaines (validations/rejets) ne sont jamais écrasées par
  l'application d'un pack.

Acquis v0.3 :

- **Détection de cartographies** : heuristique axe monotone + bloc régulier,
  confiance plafonnée à 85 % avec justification, validation/rejet humains
  persistants, vue 2D à gradient thermique (ADR-0007).
- **Comparaison hexadécimale côte à côte** : défilement synchronisé,
  différences surlignées, navigation zone par zone.
- **Annotations & favoris** : notes persistantes sur plages d'octets,
  surlignage dans la vue hexadécimale, saut direct, « Aller à l'offset ».
- Statistiques binaires : entropie par bloc, histogramme.

Acquis v0.2 :

- Noyau applicatif modulaire : configuration validée, journalisation complète,
  bus d'événements, registre de services, système de plugins (entry points).
- Base SQLite (WAL) migrée par Alembic, sauvegardes automatiques horodatées.
- Dossier véhicule en onglets : fiche, projets, **timeline d'historique**
  (interventions, diagnostics, essais routiers, datalogs, calibrations),
  **documents** (photos, factures — stockés dédupliqués, exportables).
- **Bibliothèque ECU globale** : recherche instantanée sur nom, SHA-256,
  format, véhicule ; **versioning** original → versions modifiées.
- Import de fichiers ECU : stockage adressé par contenu (SHA-256, dédupliqué,
  binaires immuables), identification de format extensible par plugins.
- Moteur de comparaison binaire vectorisé (NumPy) avec zones de différences.
- Interface sombre PySide6 : docks déplaçables, onglets, vue hexadécimale,
  glisser-déposer, raccourcis clavier, journal intégré, imports multithreadés.
- 93 tests automatiques (services, base, blobs, diff, formats, détection,
  packs, assistant IA, rapports/PDF, UI offscreen).

Voir [docs/ROADMAP.md](docs/ROADMAP.md) pour les versions suivantes et
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pour la conception détaillée.

## Essayer en une commande

Le plus simple, avec des données de démonstration pré-remplies :

```bash
# Windows : double-cliquez run.bat (ou en console)
run.bat

# Linux / macOS
./run.sh
```

Le script crée l'environnement virtuel, installe l'application et la lance.
Au premier démarrage, un véhicule de démonstration complet (Golf 7 GTI avec
projets, historique, fichiers ECU, cartographie validée) est créé pour que
vous ayez tout de suite quelque chose à explorer.

Pré-requis : **Python 3.13** installé. Sous Linux, quelques bibliothèques Qt
peuvent être nécessaires (`libegl1 libgl1 libxkbcommon0 libfontconfig1`).

## Installation manuelle (développement)

```bash
cd calforge
python3.13 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Lancer l'application

```bash
.venv/bin/python -m calforge            # démarrage normal
.venv/bin/python -m calforge --seed-demo # avec données de démonstration
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
| `Ctrl+L`  | Bibliothèque ECU globale |
| `Ctrl+M`  | Map Packs (sources de définitions) |
| `Ctrl+J`  | Assistant IA |
| `Ctrl+F`  | Recherche instantanée |
| `Ctrl+Q`  | Quitter |

## Où sont mes données ?

- **Données** (base + binaires + sauvegardes) : répertoire utilisateur standard
  (`%LOCALAPPDATA%\CalForge` sous Windows, `~/.local/share/CalForge` sous Linux).
- **Configuration** : `calforge.toml` dans le répertoire de configuration utilisateur.
- **Journaux** : répertoire de logs utilisateur, rotation automatique.

Les binaires ECU importés sont stockés en lecture seule et vérifiés par empreinte
SHA-256 : un original ne peut jamais être altéré silencieusement.
