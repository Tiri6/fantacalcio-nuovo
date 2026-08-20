#!/bin/bash
# Prepara l'ambiente delle sessioni Claude Code sul web: crea il virtualenv e
# installa le dipendenze, cosi' pytest, ruff e streamlit sono subito pronti.
set -euo pipefail

# In locale l'ambiente se lo gestisce lo sviluppatore (venv, conda, ...).
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# La radice del progetto e' due livelli sopra questo script (.claude/hooks/).
RADICE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RADICE"

# Virtualenv invece del Python di sistema: alcune dipendenze (supabase -> PyJWT)
# collidono con i pacchetti installati da Debian nell'immagine.
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

# pip e' idempotente: su una sessione ripresa non reinstalla nulla.
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements-dev.txt

# Rende il venv e il package attivi per tutti i comandi della sessione.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$RADICE/.venv\""
    echo "export PATH=\"$RADICE/.venv/bin:\$PATH\""
    echo "export PYTHONPATH=\"$RADICE\${PYTHONPATH:+:\$PYTHONPATH}\""
  } >> "$CLAUDE_ENV_FILE"
fi

# Genera subito il database di demo, cosi' l'app parte senza credenziali.
.venv/bin/python -m fantacalcio.demo_data

echo "Ambiente pronto in $RADICE/.venv (pytest, ruff, streamlit)"
