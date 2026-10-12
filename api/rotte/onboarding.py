"""I due passi fra «ho un account» e «vedo il mio fantacalcio».

Streamlit li chiamava **cancelli**: `richiedi_lega` e `richiedi_squadra`
fermavano la pagina finche' non erano superati. Qui sono rotte, e a fermare
la pagina ci pensa React — ma la sequenza e' la stessa, e per la stessa
ragione: da li' in giu' il sito da' per scontato che ci sia una lega.

Il secondo passo si puo' **saltare**: chi amministra e basta non e' obbligato
ad avere una squadra, e obbligarlo lo chiuderebbe fuori dal suo gestionale.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio.autenticazione import Ruolo, assegna_squadra, entra_in_lega
from fantacalcio.data import (
    archivio,
    carica_credenziali,
    carica_inviti,
    carica_leghe,
    carica_rose,
    prossimo_id,
    salva_credenziali,
    salva_invito,
    salva_lega,
    salva_squadra,
)
from fantacalcio.identita import ColoreNonValido, IdentitaSquadra, StileMaglia
from fantacalcio.leghe import (
    FormatoCampionato,
    LegaNonValida,
    Modalita,
    OpzioniLega,
    StatoInvito,
    crea_lega,
    invito_per_email,
    moduli_disponibili,
    trova_per_codice,
)
from fantacalcio.modelli import Squadra

from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["onboarding"])

NON_ELABORABILE = 422


class Voce(BaseModel):
    nome: str
    etichetta: str


class InvitoTrovato(BaseModel):
    """Un invito che aspetta questa persona, riconosciuto dalla sua email."""

    lega_nome: str
    codice: str


class StatoOnboarding(BaseModel):
    """Cosa manca a questa persona prima di poter usare il sito.

    Una stringa e non due booleani: i due passi sono in sequenza, e due
    booleani lascerebbero rappresentare «ha la squadra ma non la lega», che
    non puo' esistere.
    """

    serve: str  # "lega" | "squadra" | "niente"
    nome: str
    nome_lega: str
    codice_invito: str
    esistono_leghe: bool
    invito: InvitoTrovato | None
    modalita: list[Voce]
    formati: list[Voce]
    stili_maglia: list[Voce]


def _invito_che_aspetta(utente) -> InvitoTrovato | None:
    """L'invito gia' mandato a questa email, se c'e'.

    Chi e' stato invitato non deve andare a cercare il codice in chat: il
    sito sa gia' che lo aspettano, e glielo dice.
    """
    if not utente.email:
        return None
    arch = archivio()
    for lega in carica_leghe(arch).values():
        invito = invito_per_email(carica_inviti(arch, lega.id), lega.id, utente.email)
        if invito is not None:
            return InvitoTrovato(lega_nome=lega.nome, codice=lega.codice_invito)
    return None


@rotte.get("/onboarding", response_model=StatoOnboarding)
def stato(utente: UtenteDentro) -> StatoOnboarding:
    arch = archivio()
    leghe = carica_leghe(arch)
    sua = leghe.get(utente.lega_id) if utente.lega_id else None

    if sua is None:
        serve = "lega"
    elif not utente.ha_squadra:
        serve = "squadra"
    else:
        serve = "niente"

    return StatoOnboarding(
        serve=serve,
        nome=utente.nome,
        nome_lega=sua.nome if sua else "",
        codice_invito=sua.codice_invito if sua else "",
        esistono_leghe=bool(leghe),
        invito=_invito_che_aspetta(utente) if sua is None else None,
        modalita=[Voce(nome=m.name, etichetta=m.etichetta) for m in Modalita],
        formati=[Voce(nome=f.name, etichetta=f.etichetta) for f in FormatoCampionato],
        stili_maglia=[Voce(nome=s.name, etichetta=s.value) for s in StileMaglia],
    )


class NuovaLega(BaseModel):
    """Le poche scelte che vale la pena fare adesso.

    Le altre trenta opzioni restano ai valori del regolamento e si cambiano
    da «Impostazioni lega»: chiederle tutte a chi sta ancora entrando vuol
    dire farlo rinunciare a meta' strada.
    """

    nome: str = Field(min_length=1, max_length=60)
    stagione: str = Field(default="2026/27", min_length=1, max_length=20)
    # Mantra, e non per caso: e' la modalita' in cui gioca questa lega, e
    # partire dall'altra vuol dire che chi non guarda crea la lega sbagliata.
    modalita: str = Modalita.MANTRA.name
    formato: str = FormatoCampionato.ANDATA_RITORNO.name
    partecipanti: int = Field(default=10, ge=2, le=20)
    coppa_italia: bool = False
    f1_rush: bool = False


class LegaCreata(BaseModel):
    nome: str
    codice_invito: str


@rotte.post(
    "/onboarding/lega", response_model=LegaCreata, status_code=status.HTTP_201_CREATED
)
def crea(richiesta: NuovaLega, utente: UtenteDentro) -> LegaCreata:
    """Crea la lega e ne fa presidente chi l'ha creata."""
    arch = archivio()
    if utente.lega_id:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Sei gia' in una lega: non se ne possono avere due.",
        )

    credenziali = carica_credenziali(arch).get(utente.nome_utente)
    if credenziali is None:  # pragma: no cover - la sessione e' appena caduta
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Rientra nel sito."
        )

    try:
        modalita = Modalita[richiesta.modalita]
        opzioni = OpzioniLega(
            modalita=modalita,
            formato=FormatoCampionato[richiesta.formato],
            partecipanti=richiesta.partecipanti,
            coppa_italia=richiesta.coppa_italia,
            f1_rush=richiesta.f1_rush,
            # I moduli seguono la modalita': quelli predefiniti sono i Mantra,
            # e lasciarli su una lega Classic la farebbe rifiutare da se'.
            moduli_ammessi=moduli_disponibili(modalita),
        )
        lega = crea_lega(
            id_=prossimo_id(arch, "leghe"),
            nome=richiesta.nome,
            admin_id=utente.id,
            opzioni=opzioni,
            stagione=richiesta.stagione,
        )
    except (KeyError, LegaNonValida) as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    try:
        salva_lega(arch, lega)
        # Chi crea la lega la amministra: altrimenti nascerebbe una lega che
        # nessuno puo' configurare.
        salva_credenziali(arch, entra_in_lega(credenziali, lega.id, Ruolo.PRESIDENTE))
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Non riesco a salvare la lega: {errore}",
        ) from errore

    return LegaCreata(nome=lega.nome, codice_invito=lega.codice_invito)


class Codice(BaseModel):
    codice: str


@rotte.post("/onboarding/unisciti", response_model=LegaCreata)
def unisciti(richiesta: Codice, utente: UtenteDentro) -> LegaCreata:
    """Entra in una lega che esiste, col codice che gira nel gruppo."""
    arch = archivio()
    if utente.lega_id:
        raise HTTPException(status_code=NON_ELABORABILE, detail="Sei gia' in una lega.")

    lega = trova_per_codice(carica_leghe(arch), richiesta.codice)
    if lega is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Nessuna lega con questo codice. Controlla di averlo copiato "
                "per intero: sono otto caratteri."
            ),
        )

    credenziali = carica_credenziali(arch).get(utente.nome_utente)
    if credenziali is None:  # pragma: no cover - la sessione e' appena caduta
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Rientra nel sito."
        )

    try:
        salva_credenziali(arch, entra_in_lega(credenziali, lega.id))
        # Se c'era un invito per la sua email, adesso e' accettato: lasciarlo
        # «in attesa» farebbe credere al presidente che non sia mai entrato.
        if utente.email:
            invito = invito_per_email(carica_inviti(arch, lega.id), lega.id, utente.email)
            if invito is not None:
                from dataclasses import replace

                salva_invito(arch, replace(invito, stato=StatoInvito.ACCETTATO))
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Non riesco a entrare nella lega: {errore}",
        ) from errore

    return LegaCreata(nome=lega.nome, codice_invito=lega.codice_invito)


class NuovaSquadra(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    citta: str = Field(default="", max_length=60)
    stadio: str = Field(default="", max_length=80)
    curva: str = Field(default="", max_length=60)
    motto: str = Field(default="", max_length=120)
    colore_primario: str = "#2e7d32"
    colore_secondario: str = "#ffffff"
    stile_maglia: str = StileMaglia.TINTA_UNITA.name


class SquadraFondata(BaseModel):
    id: int
    nome: str


@rotte.post(
    "/onboarding/squadra",
    response_model=SquadraFondata,
    status_code=status.HTTP_201_CREATED,
)
def fonda(richiesta: NuovaSquadra, utente: UtenteDentro) -> SquadraFondata:
    """Fonda la propria squadra dentro la lega.

    Diversa da `POST /api/squadre`, che e' del presidente e crea la squadra
    di qualcun altro: questa crea **la tua** e te la assegna. Senza
    l'assegnazione la squadra esisterebbe senza proprietario, e il sito
    continuerebbe a chiedere di fondarne una.
    """
    arch = archivio()
    if not utente.lega_id:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Prima entra in una lega, poi fonda la squadra.",
        )
    if utente.ha_squadra:
        raise HTTPException(status_code=NON_ELABORABILE, detail="Hai gia' una squadra.")

    pulito = richiesta.nome.strip()
    esistenti = carica_rose(arch)
    if any(r.squadra.nome.strip().lower() == pulito.lower() for r in esistenti.values()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Esiste gia' una squadra chiamata «{pulito}».",
        )

    credenziali = carica_credenziali(arch).get(utente.nome_utente)
    if credenziali is None:  # pragma: no cover - la sessione e' appena caduta
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Rientra nel sito."
        )

    try:
        identita = IdentitaSquadra(
            presidente=utente.nome_completo,
            motto=richiesta.motto.strip(),
            stadio=richiesta.stadio.strip(),
            citta=richiesta.citta.strip(),
            curva=richiesta.curva.strip(),
            colore_primario=richiesta.colore_primario,
            colore_secondario=richiesta.colore_secondario,
            stile_maglia=StileMaglia[richiesta.stile_maglia],
        )
    except (ColoreNonValido, KeyError) as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    nuovo_id = prossimo_id(arch, "squadre")
    try:
        salva_squadra(
            arch,
            Squadra(
                id=nuovo_id,
                nome=pulito,
                presidente=identita.presidente,
                identita=identita,
                lega_id=utente.lega_id,
            ),
        )
        salva_credenziali(arch, assegna_squadra(credenziali, nuovo_id))
    except Exception as errore:  # noqa: BLE001 - i backend alzano tipi diversi
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Non riesco a salvare la squadra: {errore}",
        ) from errore

    return SquadraFondata(id=nuovo_id, nome=pulito)
