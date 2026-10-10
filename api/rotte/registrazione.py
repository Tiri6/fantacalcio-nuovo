"""Registrarsi da soli: chi arriva sul sito si crea l'account.

Il primo che si registra diventa **presidente di lega**: senza, un database
appena creato non avrebbe nessuno che possa fondare la lega, invitare gli
altri e ratificare gli scambi.

Nessuna regola nuova vive qui. Nome utente, password, email e data di nascita
li validano `autenticazione.registra` e `anagrafica.leggi_data_italiana`,
esattamente come nella versione Streamlit: due copie delle stesse regole
divergerebbero, e divergerebbero in silenzio.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from fantacalcio.anagrafica import (
    ETA_MINIMA,
    DataNonValida,
    Sesso,
    leggi_data_italiana,
    squadra_valida,
    squadre_preferite,
)
from fantacalcio.autenticazione import (
    LUNGHEZZA_MINIMA_PASSWORD,
    EmailGiaUsata,
    NomeUtenteOccupato,
    PasswordNonValida,
    Ruolo,
    UtenteNonValido,
    registra,
)
from fantacalcio.data import (
    archivio,
    carica_credenziali,
    prossimo_id,
    salva_credenziali,
)
from fantacalcio.leghe import EmailNonValida

from ..sicurezza import posa_sessione
from .accesso import ChiSono, _chi_sono

rotte = APIRouter(tags=["accesso"])

# Il nome `HTTP_422_UNPROCESSABLE_ENTITY` e' deprecato nelle Starlette
# recenti, che lo hanno rinominato. Il numero no: vedi `identita.py`.
NON_ELABORABILE = 422


class Voce(BaseModel):
    nome: str
    etichetta: str


class ModuloRegistrazione(BaseModel):
    """Quello che serve a disegnare il modulo, senza indovinare niente.

    Le tendine arrivano dal dominio: l'elenco delle squadre del cuore e' quello
    vero della stagione quando il listone e' caricato, e i sessi sono i membri
    dell'enum. Cablarli nel front-end vorrebbe dire aggiornarli in due posti.
    """

    primo_utente: bool
    sessi: list[Voce]
    squadre_preferite: list[str]
    password_minima: int
    eta_minima: int


def _club_dal_listone() -> list[str]:
    """I club di Serie A dal listone caricato, se c'e'.

    Gemella di quella in `schermate.py`: quando il listone ufficiale e'
    importato l'elenco e' quello vero della stagione, e nessuno deve
    ricordarsi di aggiornarlo a settembre.
    """
    try:
        giocatori = archivio().giocatori()
    except Exception:  # noqa: BLE001 - senza database si usa l'elenco predefinito
        return []
    if giocatori.empty or "club" not in giocatori.columns:
        return []
    return sorted({str(c).strip() for c in giocatori["club"] if str(c).strip()})


@rotte.get("/registrazione", response_model=ModuloRegistrazione)
def modulo() -> ModuloRegistrazione:
    return ModuloRegistrazione(
        primo_utente=not carica_credenziali(archivio()),
        sessi=[Voce(nome=s.name, etichetta=s.etichetta) for s in Sesso],
        squadre_preferite=squadre_preferite(_club_dal_listone()),
        password_minima=LUNGHEZZA_MINIMA_PASSWORD,
        eta_minima=ETA_MINIMA,
    )


class Iscrizione(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    cognome: str = Field(min_length=1, max_length=60)
    # Come la scrive una persona: «24/03/1991». La converte il dominio, che
    # accetta anche '-', '.' e lo spazio come separatori.
    data_nascita: str
    sesso: str = Sesso.NON_DICHIARATO.name
    citta: str = Field(min_length=1, max_length=60)
    squadra_preferita: str = ""
    nome_utente: str
    email: str
    password: str
    conferma: str


@rotte.post("/registrazione", response_model=ChiSono, status_code=status.HTTP_201_CREATED)
def iscriviti(richiesta: Iscrizione, risposta: Response) -> ChiSono:
    """Crea l'account e fa entrare subito.

    Entrare subito e non «ora rientra con le credenziali»: l'utente le ha
    appena scelte, rimandarlo al modulo di accesso e' un passaggio che non
    serve a niente e che a qualcuno fa credere che qualcosa sia andato storto.
    """
    arch = archivio()
    esistenti = carica_credenziali(arch)

    try:
        data_nascita = leggi_data_italiana(richiesta.data_nascita)
    except DataNonValida as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    try:
        sesso = Sesso[richiesta.sesso]
    except KeyError:
        sesso = Sesso.NON_DICHIARATO

    try:
        nuove = registra(
            credenziali_esistenti=esistenti,
            id_=prossimo_id(arch, "utenti"),
            nome_utente=richiesta.nome_utente,
            nome=richiesta.nome,
            cognome=richiesta.cognome,
            password=richiesta.password,
            conferma=richiesta.conferma,
            email=richiesta.email,
            data_nascita=data_nascita,
            sesso=sesso,
            citta=richiesta.citta,
            squadra_preferita=squadra_valida(
                richiesta.squadra_preferita, squadre_preferite(_club_dal_listone())
            ),
            # Il primo che arriva amministra: un database senza presidente non
            # potrebbe nemmeno creare la lega.
            ruolo=Ruolo.PRESIDENTE if not esistenti else Ruolo.FANTALLENATORE,
        )
    except (
        NomeUtenteOccupato,
        EmailGiaUsata,
        UtenteNonValido,
        PasswordNonValida,
        EmailNonValida,
    ) as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    try:
        salva_credenziali(arch, nuove)
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        # Il caso quasi sempre vero: chiave `anon` invece di `service_role`, e
        # la Row Level Security blocca ogni scrittura. Dirlo qui fa risparmiare
        # mezz'ora a chi pubblica.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Non riesco a scrivere sul database. Se il sito e' appena "
                "stato pubblicato, controlla di aver messo la chiave "
                "`service_role` di Supabase e non la `anon`: con quella la "
                "Row Level Security blocca tutte le scritture."
            ),
        ) from errore

    posa_sessione(risposta, nuove.utente.nome_utente)
    return _chi_sono(nuove.utente)
