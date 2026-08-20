#!/bin/bash
# Sposta il progetto dalla sottocartella di virtual-nutritionist a un repo
# dedicato, CONSERVANDO la storia dei commit.
#
# Prima di lanciarlo: crea su GitHub un repository vuoto (senza README, senza
# .gitignore) e passane l'URL come argomento.
#
#   ./scripts/migra_in_repo_dedicato.sh git@github.com:Tiri6/fantacalcio-nuovo.git
#
# Va eseguito dalla cartella `fantacalcio/` del repo virtual-nutritionist.
set -euo pipefail

DESTINAZIONE="${1:-}"
if [ -z "$DESTINAZIONE" ]; then
  echo "Uso: $0 <url-del-nuovo-repository>" >&2
  echo "Esempio: $0 git@github.com:Tiri6/fantacalcio-nuovo.git" >&2
  exit 1
fi

RADICE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOTTOCARTELLA="fantacalcio"
RAMO_TEMPORANEO="solo-fantacalcio-$$"

cd "$RADICE"

if [ -n "$(git status --porcelain)" ]; then
  echo "Ci sono modifiche non committate: sistemale prima di migrare." >&2
  git status --short >&2
  exit 1
fi

echo "1/4  Estraggo la storia della sottocartella '$SOTTOCARTELLA'..."
# subtree split riscrive i commit che toccano la sottocartella spostando i
# percorsi alla radice: la storia resta, i file non sono piu' annidati.
git subtree split --prefix="$SOTTOCARTELLA" -b "$RAMO_TEMPORANEO" >/dev/null

COMMIT=$(git rev-list --count "$RAMO_TEMPORANEO")
echo "     $COMMIT commit estratti."

echo "2/4  Preparo una copia pulita..."
LAVORO=$(mktemp -d)
git clone --quiet --no-local --branch "$RAMO_TEMPORANEO" . "$LAVORO/fantacalcio-nuovo"

cd "$LAVORO/fantacalcio-nuovo"
git branch -m "$RAMO_TEMPORANEO" main
git remote remove origin

echo "3/4  Collego il nuovo repository..."
git remote add origin "$DESTINAZIONE"

echo "4/4  Push su main..."
git push -u origin main

cd "$RADICE"
git branch -D "$RAMO_TEMPORANEO" >/dev/null

echo
echo "Fatto. Il progetto vive ora in $DESTINAZIONE"
echo "La copia di lavoro e' in: $LAVORO/fantacalcio-nuovo"
echo
echo "Prossimi passi:"
echo "  - Settings -> Collaborators: aggiungi il tuo amico"
echo "  - Cancella la cartella 'fantacalcio/' da virtual-nutritionist"
echo "    (git rm -r fantacalcio && git commit -m 'Sposta il gestionale nel suo repo')"
