"""Genera la SQL per reimpostare una password quando si e' chiusi fuori.

Serve nell'unico caso che l'app non puo' risolvere da sola: il presidente ha
dimenticato la propria password ed e' l'unico che potrebbe reimpostarla. Da
dentro il sito non c'e' via d'uscita; da qui si', perche' si scrive
direttamente sul database.

    python scripts/reimposta_password.py marco
    python scripts/reimposta_password.py marco --password "quella che voglio"

Stampa una UPDATE da incollare nel SQL Editor di Supabase. La password nuova
nasce con `deve_cambiare_password` alzato: al primo accesso il sito obbliga a
sostituirla, quindi quella generata qui vive pochi minuti.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fantacalcio.autenticazione import (  # noqa: E402
    cifra_password,
    controlla_password,
    genera_password_temporanea,
    normalizza_nome_utente,
)


def sql_per(nome_utente: str, password: str) -> str:
    hash_password, sale = cifra_password(password)
    utente = normalizza_nome_utente(nome_utente)
    return (
        "update utenti set\n"
        f"    hash_password = '{hash_password}',\n"
        f"    sale = '{sale}',\n"
        "    deve_cambiare_password = true\n"
        f"where nome_utente = '{utente}';"
    )


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("nome_utente", help="il nome utente da sbloccare")
    argomenti.add_argument(
        "--password",
        help="password da impostare. Senza, se ne genera una temporanea.",
    )
    scelte = argomenti.parse_args()

    password = scelte.password or genera_password_temporanea()
    controlla_password(password)

    print("Password da usare per entrare:\n")
    print(f"    {password}\n")
    print("Incolla questa query nel SQL Editor di Supabase:\n")
    print(sql_per(scelte.nome_utente, password))
    print(
        "\nPoi entra col nome utente e questa password: il sito ti chiedera' "
        "subito di sceglierne una tua."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
