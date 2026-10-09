"""La bacheca della lega: leggere, scrivere, correggere, cancellare.

E' la pagina d'ingresso: chi entra vuole sapere cosa e' successo, non leggere
una tabella di contratti.

**Il testo esce da qui come Markdown grezzo, mai come HTML.** Lo scrive una
persona, e trasformarlo in markup qui dentro vorrebbe dire che il front-end
se lo ritrova da piazzare in un `dangerouslySetInnerHTML`: da li' chi scrive
un annuncio potrebbe infilare uno `<script>` nella pagina di tutti gli altri.
Il front-end lo rende con un lettore di Markdown che l'HTML non lo esegue.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from fantacalcio.bacheca import (
    TESTO_MASSIMO,
    TITOLO_MASSIMO,
    TITOLO_MINIMO,
    Annuncio,
    AnnuncioNonValido,
    NonAutorizzato,
    TipoAnnuncio,
    crea_annuncio,
    modifica,
    puo_pubblicare,
    visibili_per,
)
from fantacalcio.data import (
    carica_annunci,
    elimina_annuncio,
    prossimo_id,
    salva_annuncio,
)

from ..contesto import contesto_di
from ..dipendenze import UtenteDentro

rotte = APIRouter(tags=["bacheca"])

NON_ELABORABILE = 422


class AnnuncioLetto(BaseModel):
    id: int
    titolo: str
    # Markdown grezzo: vedi la nota in cima al file.
    testo: str
    tipo: str
    tipo_etichetta: str
    tipo_icona: str
    autore_nome: str
    giornata: int | None
    pubblicato: bool
    in_evidenza: bool
    # Gia' in italiano e gia' leggibile: la stessa funzione del dominio che
    # usa Streamlit, cosi' le due facciate scrivono la data allo stesso modo.
    data_leggibile: str


class TipoDisponibile(BaseModel):
    nome: str
    etichetta: str
    icona: str


class Bacheca(BaseModel):
    annunci: list[AnnuncioLetto]
    tipi: list[TipoDisponibile]
    # Il permesso lo dice il dominio (`bacheca.puo_pubblicare`), non il
    # front-end: nascondere il modulo non e' un controllo, e infatti ogni
    # rotta di scrittura qui sotto lo richiede di nuovo.
    posso_scrivere: bool
    nome_lega: str
    titolo_minimo: int
    titolo_massimo: int
    testo_massimo: int


class Scritto(BaseModel):
    titolo: str = Field(min_length=TITOLO_MINIMO, max_length=TITOLO_MASSIMO)
    testo: str = Field(min_length=1, max_length=TESTO_MASSIMO)
    tipo: str = TipoAnnuncio.NOTIZIA.name
    giornata: int | None = Field(default=None, ge=1, le=76)
    pubblicato: bool = True
    in_evidenza: bool = False


def _letto(annuncio: Annuncio) -> AnnuncioLetto:
    return AnnuncioLetto(
        id=annuncio.id,
        titolo=annuncio.titolo,
        testo=annuncio.testo,
        tipo=annuncio.tipo.name,
        tipo_etichetta=annuncio.tipo.etichetta,
        tipo_icona=annuncio.tipo.icona,
        autore_nome=annuncio.autore_nome,
        giornata=annuncio.giornata,
        pubblicato=annuncio.pubblicato,
        in_evidenza=annuncio.in_evidenza,
        data_leggibile=annuncio.data_leggibile,
    )


def _tipo_o_422(nome: str) -> TipoAnnuncio:
    try:
        return TipoAnnuncio[nome]
    except KeyError:
        raise HTTPException(
            status_code=NON_ELABORABILE, detail=f"Tipo di annuncio sconosciuto: {nome}"
        ) from None


@rotte.get("/bacheca", response_model=Bacheca)
def leggi(utente: UtenteDentro) -> Bacheca:
    ctx = contesto_di(utente)
    lega_id = ctx.lega.id if ctx.lega else None
    # `visibili_per` tiene fuori gli annunci delle altre leghe e mostra le
    # bozze solo a chi amministra: cosi' il recap si prepara prima che la
    # giornata sia chiusa, senza che nessun altro lo veda.
    annunci = visibili_per(carica_annunci(ctx.arch, lega_id), utente, ctx.lega)
    return Bacheca(
        annunci=[_letto(a) for a in annunci],
        tipi=[
            TipoDisponibile(nome=t.name, etichetta=t.etichetta, icona=t.icona)
            for t in TipoAnnuncio
        ],
        posso_scrivere=puo_pubblicare(utente, ctx.lega),
        nome_lega=ctx.lega.nome if ctx.lega else "",
        titolo_minimo=TITOLO_MINIMO,
        titolo_massimo=TITOLO_MASSIMO,
        testo_massimo=TESTO_MASSIMO,
    )


def _annuncio_o_404(ctx, annuncio_id: int) -> Annuncio:
    lega_id = ctx.lega.id if ctx.lega else None
    for annuncio in carica_annunci(ctx.arch, lega_id):
        if annuncio.id == annuncio_id:
            return annuncio
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Annuncio inesistente."
    )


@rotte.post("/bacheca", response_model=AnnuncioLetto, status_code=status.HTTP_201_CREATED)
def scrivi(richiesta: Scritto, utente: UtenteDentro) -> AnnuncioLetto:
    ctx = contesto_di(utente)
    if ctx.lega is None:
        raise HTTPException(
            status_code=NON_ELABORABILE,
            detail="Un annuncio appartiene a una lega, e tu non ne hai una.",
        )

    try:
        nuovo = crea_annuncio(
            id_=prossimo_id(ctx.arch, "annunci"),
            lega=ctx.lega,
            utente=utente,
            titolo=richiesta.titolo,
            testo=richiesta.testo,
            tipo=_tipo_o_422(richiesta.tipo),
            giornata=richiesta.giornata,
            pubblicato=richiesta.pubblicato,
            in_evidenza=richiesta.in_evidenza,
        )
    except NonAutorizzato as errore:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(errore)
        ) from errore
    except AnnuncioNonValido as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    salva_annuncio(ctx.arch, nuovo)
    return _letto(nuovo)


class Correzione(BaseModel):
    """Solo i campi mandati cambiano.

    Serve a far funzionare i bottoni rapidi («metti in evidenza», «riporta a
    bozza») senza rispedire tutto l'annuncio: rimandarlo per intero vorrebbe
    dire che due persone che premono due bottoni diversi nello stesso minuto
    si sovrascrivono il testo a vicenda.
    """

    titolo: str | None = Field(
        default=None, min_length=TITOLO_MINIMO, max_length=TITOLO_MASSIMO
    )
    testo: str | None = Field(default=None, min_length=1, max_length=TESTO_MASSIMO)
    tipo: str | None = None
    giornata: int | None = Field(default=None, ge=0, le=76)
    pubblicato: bool | None = None
    in_evidenza: bool | None = None


@rotte.put("/bacheca/{annuncio_id}", response_model=AnnuncioLetto)
def correggi(
    annuncio_id: int, richiesta: Correzione, utente: UtenteDentro
) -> AnnuncioLetto:
    ctx = contesto_di(utente)
    annuncio = _annuncio_o_404(ctx, annuncio_id)

    campi = richiesta.model_dump(exclude_none=True)
    if "tipo" in campi:
        campi["tipo"] = _tipo_o_422(campi["tipo"])
    if campi.get("giornata") == 0:
        # Zero vuol dire «nessuna giornata in particolare», come nel modulo.
        campi["giornata"] = None

    try:
        corretto = modifica(annuncio, utente, ctx.lega, **campi)
    except NonAutorizzato as errore:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(errore)
        ) from errore
    except AnnuncioNonValido as errore:
        raise HTTPException(status_code=NON_ELABORABILE, detail=str(errore)) from errore

    salva_annuncio(ctx.arch, corretto)
    return _letto(corretto)


@rotte.delete("/bacheca/{annuncio_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancella(annuncio_id: int, utente: UtenteDentro) -> None:
    """Cancella davvero: un annuncio eliminato non si recupera.

    La conferma la chiede il front-end; il permesso lo chiede il dominio.
    """
    ctx = contesto_di(utente)
    annuncio = _annuncio_o_404(ctx, annuncio_id)
    if not puo_pubblicare(utente, ctx.lega):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo chi amministra la lega puo' cancellare dalla bacheca.",
        )
    elimina_annuncio(ctx.arch, annuncio.id)
