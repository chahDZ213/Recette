#!/usr/bin/env bash
# One-command launcher for CalForge (Linux / macOS).
# Creates a virtualenv on first run, installs the app, then launches it.
# First launch seeds demo data so you have something to explore immediately.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3.13}"
if ! command -v "$PY" >/dev/null 2>&1; then
  PY="python3"
fi

if [ ! -d .venv ]; then
  echo "Création de l'environnement virtuel…"
  "$PY" -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  echo "Installation de CalForge et de ses dépendances…"
  ./.venv/bin/pip install --quiet -e .
  SEED="--seed-demo"
else
  SEED="${1:-}"
fi

echo "Lancement de CalForge…"
exec ./.venv/bin/python -m calforge $SEED
