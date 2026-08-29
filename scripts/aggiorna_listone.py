"""Scarica il listone e gli stipendi da riga di comando, senza aprire il sito.

Fa esattamente quel che fa il pulsante «Aggiorna listone» nella pagina
«Listone giocatori». Serve in tre casi:

- provare le fonti da un computer che ha rete, quando il server del sito non
  ce l'ha o e' dietro un proxy che blocca fantacalcio.it;
- vedere il file consolidato prima di scriverlo in archivio (`--csv`);
- rimettere in piedi il catalogo in fretta senza passare dal browser.

    python scripts/aggiorna_listone.py --prova
    python scripts/aggiorna_listone.py --csv listone.csv
    python scripts/aggiorna_listone.py --scrivi

Senza `--scrivi` non tocca il database: stampa e basta.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fantacalcio import fonti_web  # noqa: E402


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument(
        "--stagione",
        help="Stagione nella forma 2026_27. Senza, si deduce dalla data.",
    )
    argomenti.add_argument(
        "--csv", type=Path, help="Scrive il listone consolidato in questo file."
    )
    argomenti.add_argument(
        "--scrivi",
        action="store_true",
        help="Salva anche nel database configurato (Supabase o demo SQLite).",
    )
    argomenti.add_argument(
        "--prova",
        action="store_true",
        help="Solo le prime dieci righe, per vedere se le fonti rispondono.",
    )
    scelte = argomenti.parse_args()

    stagione = scelte.stagione or fonti_web.stagione()
    print(f"Stagione {fonti_web.etichetta_stagione(stagione)}")

    ingaggi = {}
    if scelte.scrivi:
        from fantacalcio.data import archivio, carica_giocatori

        ingaggi = {
            g.id_ufficiale: g.ingaggio
            for g in carica_giocatori(archivio()).values()
            if g.id_ufficiale is not None and g.ingaggio
        }

    esito = fonti_web.aggiorna_da_web(ingaggi_correnti=ingaggi, stagione_=stagione)

    for fonte in esito.fonti:
        print(f"  {'ok ' if fonte.ok else 'NO '} {fonte.nome}: {fonte.dettaglio}")
        print(f"      {fonte.url}")

    if not esito.riuscito:
        print("\nNiente da salvare: il listone non e' arrivato.")
        return 1

    print(
        f"\n{len(esito.righe)} giocatori, {esito.con_stipendio} con lo stipendio, "
        f"{len(esito.senza_stipendio)} senza."
    )

    if scelte.prova:
        for riga in esito.righe[:10]:
            print(
                f"  {riga.nome:<24} {riga.club:<12} {'/'.join(riga.ruoli):<10} "
                f"{riga.ingaggio / 1_000_000:>7.2f}M  {riga.nazionalita}"
            )

    if scelte.csv:
        scelte.csv.write_text(fonti_web.a_csv(esito.righe), encoding="utf-8")
        print(f"Scritto {scelte.csv}")

    if scelte.scrivi:
        from fantacalcio.data import archivio

        conteggio = fonti_web.applica(archivio(), esito.righe)
        print(f"Salvati in archivio: {conteggio['totali']} ({conteggio['nuovi']} nuovi).")
    else:
        print("Database non toccato: aggiungi --scrivi per salvare.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
