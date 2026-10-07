"""Entrare, sapere chi si e', uscire."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from fantacalcio.autenticazione import autentica
from fantacalcio.data import archivio, carica_credenziali

from ..dipendenze import UtenteDentro
from ..sicurezza import DURATA, NOME_COOKIE, crea_token

rotte = APIRouter(tags=["accesso"])


class Credenziali(BaseModel):
    nome_utente: str
    password: str


class ChiSono(BaseModel):
    nome_utente: str
    nome: str
    ruolo: str
    squadra_id: int | None
    lega_id: int | None
    deve_cambiare_password: bool
    # Mandati espliciti invece di far dedurre il ruolo al front-end: se un
    # giorno la regola cambia, cambia qui e non in ogni schermata che la
    # indovinava da `ruolo == "PRESIDENTE"`.
    puo_importare: bool
    puo_svincolare: bool
    puo_scrivere_in_bacheca: bool


def _chi_sono(utente) -> ChiSono:
    return ChiSono(
        nome_utente=utente.nome_utente,
        nome=utente.nome,
        ruolo=utente.ruolo.name,
        squadra_id=utente.squadra_id,
        lega_id=utente.lega_id,
        deve_cambiare_password=utente.deve_cambiare_password,
        puo_importare=utente.puo_importare,
        puo_svincolare=getattr(utente, "puo_svincolare", False),
        puo_scrivere_in_bacheca=utente.puo_scrivere_in_bacheca,
    )


@rotte.post("/accesso", response_model=ChiSono)
def entra(credenziali: Credenziali, risposta: Response) -> ChiSono:
    """Verifica le credenziali e posa il cookie di sessione.

    L'errore resta lo stesso sia che il nome utente non esista sia che la
    password sia sbagliata: distinguerli direbbe a chi prova quali nomi
    utente esistono.
    """
    utente = autentica(
        carica_credenziali(archivio()),
        credenziali.nome_utente,
        credenziali.password,
    )
    if utente is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome utente o password non corretti.",
        )

    risposta.set_cookie(
        NOME_COOKIE,
        crea_token(utente.nome_utente),
        max_age=int(DURATA.total_seconds()),
        httponly=True,
        # In sviluppo si gira su http://localhost, dove un cookie Secure non
        # verrebbe mai mandato indietro e il login sembrerebbe rotto.
        secure=os.environ.get("FANTA_AMBIENTE") != "sviluppo",
        samesite="lax",
        path="/",
    )
    return _chi_sono(utente)


@rotte.get("/io", response_model=ChiSono)
def io(utente: UtenteDentro) -> ChiSono:
    """Chi sta chiamando, riletto dal database. Serve a React all'avvio."""
    return _chi_sono(utente)


@rotte.post("/esci", status_code=status.HTTP_204_NO_CONTENT)
def esci(risposta: Response) -> None:
    risposta.delete_cookie(NOME_COOKIE, path="/")
