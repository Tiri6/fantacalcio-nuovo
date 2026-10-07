"""Il mio profilo: chi sono, e come cambio la password.

Due cose che si fanno da qui e che hanno la stessa forma: una password nuova
e un codice di recupero. Tutte e due esistono **in chiaro una volta sola**,
nel momento in cui si generano; da li' in poi nel database resta solo il loro
hash, come per qualunque password.

Il controllo vero lo fa il dominio: `cambia_password` pretende quella
attuale, e non e' una formalita' — senza, chiunque trovasse una sessione
aperta si prenderebbe l'account per sempre.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio.anagrafica import anni_compiuti, scrivi_data_italiana
from fantacalcio.autenticazione import (
    PasswordNonValida,
    cambia_password,
    con_codice_recupero,
)
from fantacalcio.data import carica_credenziali, carica_rose, salva_credenziali

from ..contesto import contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["profilo"])

NON_ELABORABILE = 422


class Profilo(BaseModel):
    nome_utente: str
    nome_completo: str
    ruolo: str
    ruolo_etichetta: str
    squadra: str
    nome_lega: str
    email: str
    data_nascita: str
    eta: int | None
    sesso: str
    citta: str
    squadra_preferita: str
    # Vero quando un codice di recupero e' gia' stato generato. Il codice in
    # se' non torna mai: esiste in chiaro solo nell'istante in cui nasce.
    ha_codice_recupero: bool


class CambioPassword(BaseModel):
    attuale: str
    nuova: str = Field(min_length=1)
    conferma: str


class CodiceGenerato(BaseModel):
    """Il codice in chiaro. E' l'unica volta che lo si vede."""

    codice: str


def _credenziali_o_401(utente):
    trovate = carica_credenziali(contesto_di(utente).arch).get(utente.nome_utente)
    if trovate is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Questo utente non esiste piu'.",
        )
    return trovate


@rotte.get("/profilo", response_model=Profilo)
def profilo(utente: UtenteDentro) -> Profilo:
    ctx = contesto_di(utente)
    credenziali = _credenziali_o_401(utente)

    squadra = "— nessuna —"
    if utente.squadra_id is not None:
        rosa = carica_rose(ctx.arch).get(utente.squadra_id)
        if rosa is not None:
            squadra = rosa.squadra.nome

    return Profilo(
        nome_utente=utente.nome_utente,
        nome_completo=utente.nome_completo,
        ruolo=utente.ruolo.name,
        ruolo_etichetta=utente.ruolo.etichetta,
        squadra=squadra,
        nome_lega=ctx.lega.nome if ctx.lega else "",
        email=utente.email or "",
        data_nascita=scrivi_data_italiana(utente.data_nascita) or "",
        eta=anni_compiuti(utente.data_nascita) if utente.data_nascita else None,
        sesso=utente.sesso.etichetta,
        citta=utente.citta or "",
        squadra_preferita=utente.squadra_preferita or "",
        ha_codice_recupero=bool(credenziali.hash_recupero),
    )


@rotte.put("/profilo/password", status_code=status.HTTP_204_NO_CONTENT)
def cambia(richiesta: CambioPassword, utente: UtenteDentro) -> None:
    """Cambio autonomo: serve conoscere la password attuale."""
    ctx = contesto_di(utente)
    credenziali = _credenziali_o_401(utente)

    try:
        aggiornate = cambia_password(
            credenziali, richiesta.attuale, richiesta.nuova, richiesta.conferma
        )
    except PasswordNonValida as errore:
        # 422 e non 403: non e' un permesso che manca, e' quello che si e'
        # scritto a non andare bene. Il messaggio arriva dal dominio, che sa
        # **quale** delle regole e' saltata.
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    salva_credenziali(ctx.arch, aggiornate)


@rotte.post("/profilo/codice-recupero", response_model=CodiceGenerato)
def genera_codice(utente: UtenteDentro) -> CodiceGenerato:
    """Genera il codice di scorta e lo restituisce **una volta sola**.

    Generarne un altro invalida il precedente: e' voluto, ed e' il motivo per
    cui la pagina lo dice prima di far premere il bottone.
    """
    ctx = contesto_di(utente)
    credenziali = _credenziali_o_401(utente)

    aggiornate, codice = con_codice_recupero(credenziali)
    salva_credenziali(ctx.arch, aggiornate)
    return CodiceGenerato(codice=codice)
