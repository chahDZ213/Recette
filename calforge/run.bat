@echo off
REM One-command launcher for CalForge (Windows).
REM Creates a virtualenv on first run, installs the app, then launches it.
REM First launch seeds demo data so you have something to explore immediately.
setlocal
cd /d "%~dp0"

set "PY=py -3.13"
%PY% --version >nul 2>&1 || set "PY=python"

if not exist ".venv" (
    echo Creation de l'environnement virtuel...
    %PY% -m venv .venv
    .venv\Scripts\python -m pip install --quiet --upgrade pip
    echo Installation de CalForge et de ses dependances...
    .venv\Scripts\pip install --quiet -e .
    set "SEED=--seed-demo"
) else (
    set "SEED=%1"
)

echo Lancement de CalForge...
.venv\Scripts\python -m calforge %SEED%
endlocal
