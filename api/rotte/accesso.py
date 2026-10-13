"""Entrare, sapere chi si e', uscire — e rientrare quando la password e' persa.

Il recupero sta qui e non in `profilo` perche' chi lo usa **non e' dentro**:
sono le uniche due rotte, con l'accesso e la registrazione, che rispondono a
chi non ha una sessione.

Tutte e due rispondono allo stesso modo che il nome utente esista o no. Una
pagina che dice «quel nome non c'e'» e' un modo comodo per farsi un elenco
di chi e' iscritto, e qui gli iscritti sono dieci persone reali.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from fantacalcio.autenticazione import (
    PasswordNonValida,
    UtenteNonValido,
    apri_richiesta_password,
    autentica,
    normalizza_nome_utente,
    recupera_con_codice,
)
from fantacalcio.data import (
    archivio,
    carica_credenziali,
    carica_richieste_password,
    prossimo_id,
    salva_credenziali,
    salva_richiesta_password,
)

from ..dipendenze import UtenteDentro
from ..sicurezza import NOME_COOKIE, posa_sessione

rotte = APIRouter(tags=["accesso"])

NON_ELABORABILE = 422


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
    # Quali competizioni gioca la lega. Servono al menu: una voce che parla di
    # una coppa che non si gioca e' peggio di una voce mancante, e il
    # front-end non puo' dedurlo dall'utente.
    gioca_coppa: bool = False
    gioca_f1_rush: bool = False


def _chi_sono(utente) -> ChiSono:
    from fantacalcio.data import carica_leghe

    lega = carica_leghe(archivio()).get(utente.lega_id) if utente.lega_id else None
    return ChiSono(
        gioca_coppa=bool(lega and lega.opzioni.coppa_italia),
        gioca_f1_rush=bool(lega and lega.opzioni.f1_rush),
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

    posa_sessione(risposta, utente.nome_utente)
    return _chi_sono(utente)


@rotte.get("/io", response_model=ChiSono)
def io(utente: UtenteDentro) -> ChiSono:
    """Chi sta chiamando, riletto dal database. Serve a React all'avvio."""
    return _chi_sono(utente)


@rotte.post("/esci", status_code=status.HTTP_204_NO_CONTENT)
def esci(risposta: Response) -> None:
    risposta.delete_cookie(NOME_COOKIE, path="/")


# ---------------------------------------------------------------------------
# Rientrare senza la password
# ---------------------------------------------------------------------------


def _adesso() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


class DaRecuperare(BaseModel):
    nome_utente: str
    codice: str
    nuova: str
    conferma: str = ""


@rotte.post("/recupero/codice", status_code=status.HTTP_204_NO_CONTENT)
def rientra_con_codice(dati: DaRecuperare) -> None:
    """Il codice di recupero, e subito una password nuova.

    Non si entra: si torna alla pagina d'accesso e si scrive la password
    appena scelta. Scriverla una volta e' la prova che chi l'ha scelta se
    l'e' anche segnata, e il codice da solo non e' un secondo fattore.

    Il codice **si consuma**: chi rientra se ne genera un altro dal profilo.
    """
    arch = archivio()
    credenziali = carica_credenziali(arch)
    try:
        trovato = credenziali.get(normalizza_nome_utente(dati.nome_utente))
    except UtenteNonValido:
        trovato = None

    try:
        if trovato is None or not trovato.utente.attivo:
            # **Identico**, punto compreso, a quello che alza
            # `recupera_con_codice`: anche solo un punto in piu' direbbe a chi
            # prova se quel nome utente esiste.
            raise PasswordNonValida("Il codice di recupero non e' corretto")
        aggiornate = recupera_con_codice(
            trovato, dati.codice, dati.nuova, dati.conferma or None
        )
    except PasswordNonValida as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    salva_credenziali(arch, aggiornate)


class DaChiedere(BaseModel):
    nome_utente: str


@rotte.post("/recupero/richiesta", status_code=status.HTTP_204_NO_CONTENT)
def chiedi_al_presidente(dati: DaChiedere) -> None:
    """Lascia scritto nel sito che qualcuno non riesce a entrare.

    Il presidente la vede nella pagina della lega, dov'e' gia' il pulsante
    per reimpostare: prima bisognava scrivergli e sperare se lo ricordasse.

    Risponde sempre 204, anche quando non c'e' niente da registrare — nome
    inesistente, utente disattivato, o una richiesta gia' aperta.
    """
    arch = archivio()
    richiesta = apri_richiesta_password(
        carica_credenziali(arch),
        dati.nome_utente,
        aperte=carica_richieste_password(arch),
        quando=_adesso(),
        prossimo_id=prossimo_id(arch, "richieste_password"),
    )
    if richiesta is not None:
        salva_richiesta_password(arch, richiesta)
