"""Le dipendenze che ogni rotta si fa dare: l'archivio e chi sta chiamando.

I permessi restano quelli del dominio — `Utente.puo_gestire`,
`puo_svincolare`, le transizioni di `scambi.py`. Qui si risponde solo a «chi
sei», e le rotte chiedono al dominio «puoi?». Un controllo scritto qui
sarebbe una seconda copia della regola, e la copia diverge.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from fantacalcio.autenticazione import Utente
from fantacalcio.data import archivio, carica_credenziali

from .sicurezza import NOME_COOKIE, leggi_token


def utente_corrente(
    # L'alias tiene il nome del cookie legato a `NOME_COOKIE`. Senza, FastAPI
    # lo ricaverebbe dal nome del parametro: due posti che dicono la stessa
    # cosa, e il giorno che la costante cambia l'accesso smette di funzionare
    # senza che niente lo segnali.
    sessione_cookie: Annotated[str | None, Cookie(alias=NOME_COOKIE)] = None,
) -> Utente:
    """L'utente di questa richiesta, riletto dal database ogni volta.

    Riletto e non ricostruito dal token: il token dice solo *chi*. Se nel
    frattempo e' entrato in una lega, ha fondato la squadra o il presidente
    gli ha cambiato il ruolo, qui si vede subito.
    """
    if not sessione_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Non sei entrato."
        )

    sessione = leggi_token(sessione_cookie)
    if sessione is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sessione non e' piu' valida: rientra.",
        )

    trovate = carica_credenziali(archivio()).get(sessione.nome_utente)
    if trovate is None or not trovate.utente.attivo:
        # Cancellato o disattivato mentre il token era ancora buono.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Questo utente non puo' piu' accedere.",
        )
    return trovate.utente


UtenteDentro = Annotated[Utente, Depends(utente_corrente)]
