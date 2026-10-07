"""Identita' delle squadre: galleria, modifica, creazione.

La maglia la disegna il dominio (`identita.maglia_svg`), non React: e' codice
gia' provato, e ridisegnarla in TypeScript vorrebbe dire che due squadre con
gli stessi colori possono venire diverse a seconda di chi le guarda.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio.data import carica_rose, prossimo_id, salva_squadra
from fantacalcio.identita import (
    ColoreNonValido,
    IdentitaSquadra,
    ImmagineNonValida,
    StileMaglia,
    immagine_a_data_uri,
)
from fantacalcio.modelli import Squadra

from ..contesto import contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["identita"])

# Il nome `HTTP_422_UNPROCESSABLE_ENTITY` e' deprecato nelle Starlette recenti
# e il suo sostituto non esiste in quelle vecchie: il numero vale per tutte.
NON_ELABORABILE = 422


def _maglia_data_uri(identita: IdentitaSquadra, larghezza: int = 180) -> str:
    """Sempre un data URI, disegnata o caricata che sia.

    Una strada sola per i due casi: cosi' il front-end mette il valore in un
    `<img src>` e non deve sapere quale dei due gli e' arrivato.
    """
    contenuto = identita.maglia(larghezza)
    if contenuto.startswith("data:"):
        return contenuto
    codificato = base64.b64encode(contenuto.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{codificato}"


class StileDisponibile(BaseModel):
    nome: str
    etichetta: str


class SquadraInGalleria(BaseModel):
    id: int
    nome: str
    presidente: str
    motto: str
    stadio: str
    citta: str
    curva: str
    anno_fondazione: int | None
    colore_primario: str
    colore_secondario: str
    stile_maglia: str
    maglia: str
    logo: str | None
    # Chi puo' metterci le mani lo dice il dominio, non il front-end.
    modificabile: bool


class Galleria(BaseModel):
    squadre: list[SquadraInGalleria]
    stili: list[StileDisponibile]
    posso_crearne: bool
    # Serve al modulo per dire «esiste gia' una squadra chiamata cosi'»
    # prima di provare a salvare.
    nomi_occupati: list[str]


class Modifica(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    presidente: str = Field(min_length=1, max_length=60)
    motto: str = Field(default="", max_length=120)
    stadio: str = Field(default="", max_length=80)
    citta: str = Field(default="", max_length=60)
    curva: str = Field(default="", max_length=60)
    colore_primario: str
    colore_secondario: str
    stile_maglia: str
    anno_fondazione: int | None = Field(default=None, ge=1900, le=2100)
    # Immagini come data URI: il dominio le conserva gia' cosi', quindi non
    # serve il multipart e i due backend si comportano allo stesso modo.
    logo: str | None = None
    maglia_caricata: str | None = None
    rimuovi_logo: bool = False
    rimuovi_maglia: bool = False


def _galleria(utente) -> Galleria:
    ctx = contesto_di(utente)
    rose = carica_rose(ctx.arch)

    squadre = []
    for rosa in rose.values():
        s = rosa.squadra
        if utente.lega_id is not None and s.lega_id not in (None, utente.lega_id):
            continue
        i = s.identita
        squadre.append(
            SquadraInGalleria(
                id=s.id,
                nome=s.nome,
                presidente=i.presidente,
                motto=i.motto,
                stadio=i.stadio,
                citta=i.citta,
                curva=i.curva,
                anno_fondazione=i.anno_fondazione,
                colore_primario=i.colore_primario,
                colore_secondario=i.colore_secondario,
                stile_maglia=i.stile_maglia.name,
                maglia=_maglia_data_uri(i),
                logo=i.logo,
                modificabile=utente.puo_gestire(s.id),
            )
        )

    squadre.sort(key=lambda s: s.nome)
    return Galleria(
        squadre=squadre,
        stili=[StileDisponibile(nome=s.name, etichetta=s.value) for s in StileMaglia],
        posso_crearne=utente.puo_importare,
        nomi_occupati=[s.nome for s in squadre],
    )


@rotte.get("/identita", response_model=Galleria)
def galleria(utente: UtenteDentro) -> Galleria:
    return _galleria(utente)


def _costruisci(modifica: Modifica, precedente: IdentitaSquadra) -> IdentitaSquadra:
    """Dalla richiesta all'identita', tenendo quel che non e' stato mandato.

    Le immagini si conservano se nessuno le tocca: senza, salvare il motto
    cancellerebbe il logo — ed e' la trappola gia' pagata una volta su questo
    progetto, quando ricostruire una dataclass perdeva i campi non nominati.
    """
    logo = precedente.logo
    if modifica.rimuovi_logo:
        logo = None
    elif modifica.logo:
        logo = modifica.logo

    maglia = precedente.maglia_caricata
    if modifica.rimuovi_maglia:
        maglia = None
    elif modifica.maglia_caricata:
        maglia = modifica.maglia_caricata

    try:
        stile = StileMaglia[modifica.stile_maglia]
    except KeyError:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail=f"Stile di maglia sconosciuto: {modifica.stile_maglia}",
        ) from None

    return IdentitaSquadra(
        presidente=modifica.presidente.strip(),
        motto=modifica.motto.strip(),
        stadio=modifica.stadio.strip(),
        citta=modifica.citta.strip(),
        curva=modifica.curva.strip(),
        colore_primario=modifica.colore_primario,
        colore_secondario=modifica.colore_secondario,
        stile_maglia=stile,
        logo=logo,
        maglia_caricata=maglia,
        anno_fondazione=modifica.anno_fondazione,
    )


def _nome_libero(nome: str, rose, escludi: int | None) -> None:
    pulito = nome.strip().lower()
    for rosa in rose.values():
        if rosa.squadra.id != escludi and rosa.squadra.nome.strip().lower() == pulito:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Esiste gia' una squadra chiamata «{nome.strip()}».",
            )


@rotte.put("/squadre/{squadra_id}/identita", response_model=SquadraInGalleria)
def modifica(
    squadra_id: int, richiesta: Modifica, utente: UtenteDentro
) -> SquadraInGalleria:
    ctx = contesto_di(utente)
    rose = carica_rose(ctx.arch)
    rosa = rose.get(squadra_id)
    if rosa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Squadra inesistente."
        )

    # Il permesso lo decide il dominio: nascondere il modulo non e' un controllo.
    if not utente.puo_gestire(squadra_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Puoi modificare solo la tua squadra.",
        )

    _nome_libero(richiesta.nome, rose, escludi=squadra_id)
    vecchia = rosa.squadra

    try:
        identita = _costruisci(richiesta, vecchia.identita)
        salva_squadra(
            ctx.arch,
            Squadra(
                id=vecchia.id,
                nome=richiesta.nome.strip(),
                presidente=identita.presidente,
                identita=identita,
                # Va riportato a mano: ricostruendo la Squadra senza, il
                # salvataggio la scollegherebbe dalla sua lega.
                lega_id=vecchia.lega_id or (ctx.lega.id if ctx.lega else None),
            ),
        )
    except (ColoreNonValido, ImmagineNonValida) as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    aggiornata = next(s for s in _galleria(utente).squadre if s.id == squadra_id)
    return aggiornata


@rotte.post(
    "/squadre", response_model=SquadraInGalleria, status_code=status.HTTP_201_CREATED
)
def crea(richiesta: Modifica, utente: UtenteDentro) -> SquadraInGalleria:
    ctx = contesto_di(utente)

    if not utente.puo_importare:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo il presidente puo' creare una squadra.",
        )

    rose = carica_rose(ctx.arch)
    _nome_libero(richiesta.nome, rose, escludi=None)

    try:
        identita = _costruisci(richiesta, IdentitaSquadra())
        nuovo_id = prossimo_id(ctx.arch, "squadre")
        salva_squadra(
            ctx.arch,
            Squadra(
                id=nuovo_id,
                nome=richiesta.nome.strip(),
                presidente=identita.presidente,
                identita=identita,
                lega_id=ctx.lega.id if ctx.lega else None,
            ),
        )
    except (ColoreNonValido, ImmagineNonValida) as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    return next(s for s in _galleria(utente).squadre if s.id == nuovo_id)


class Caricamento(BaseModel):
    contenuto_base64: str
    tipo_mime: str


class ImmagineCaricata(BaseModel):
    data_uri: str


@rotte.post("/immagini", response_model=ImmagineCaricata)
def carica_immagine(richiesta: Caricamento, utente: UtenteDentro) -> ImmagineCaricata:
    """Valida un'immagine e la restituisce come data URI.

    I controlli — formato ammesso, non vuota, sotto il peso massimo — li fa
    `identita.immagine_a_data_uri`, lo stesso codice che usa Streamlit: un
    limite riscritto qui sarebbe la copia che diverge.
    """
    try:
        grezzo = base64.b64decode(richiesta.contenuto_base64, validate=True)
    except Exception as errore:  # noqa: BLE001 - base64 alza tipi diversi
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Il file non e' leggibile.",
        ) from errore

    try:
        return ImmagineCaricata(data_uri=immagine_a_data_uri(grezzo, richiesta.tipo_mime))
    except ImmagineNonValida as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore
