"""La bacheca della lega: notizie, comunicazioni e recap di giornata.

Scrive solo chi amministra; leggono tutti. E' la parte del gestionale che non
calcola niente — serve a far esistere la lega anche fra una giornata e l'altra.

Il testo e' Markdown e resta Markdown: non viene mai passato a
`unsafe_allow_html`. Streamlit lo rende scudando l'HTML, quindi un annuncio
non puo' iniettare markup nella pagina di chi legge.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum

TITOLO_MINIMO = 3
TITOLO_MASSIMO = 120
TESTO_MASSIMO = 20_000


class AnnuncioNonValido(ValueError):
    pass


class NonAutorizzato(PermissionError):
    """Chi non amministra la lega non pubblica sulla bacheca."""


class TipoAnnuncio(Enum):
    NOTIZIA = "Notizia"
    COMUNICAZIONE = "Comunicazione"
    RECAP = "Recap di giornata"
    MERCATO = "Mercato"

    @property
    def etichetta(self) -> str:
        return self.value

    @property
    def icona(self) -> str:
        return {
            "Notizia": "📰",
            "Comunicazione": "📢",
            "Recap di giornata": "⚽",
            "Mercato": "🔁",
        }[self.value]


def _ora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Annuncio:
    """Un post della bacheca.

    `pubblicato` a False = bozza: la vede solo chi l'ha scritta. Serve a
    preparare il recap prima che la giornata sia chiusa.
    """

    id: int
    lega_id: int
    titolo: str
    testo: str
    tipo: TipoAnnuncio = TipoAnnuncio.NOTIZIA
    autore_id: int = 0
    autore_nome: str = ""
    giornata: int | None = None
    pubblicato: bool = True
    in_evidenza: bool = False
    creato_il: str = ""
    aggiornato_il: str = ""

    def __post_init__(self) -> None:
        titolo = (self.titolo or "").strip()
        if len(titolo) < TITOLO_MINIMO:
            raise AnnuncioNonValido(
                f"Il titolo deve avere almeno {TITOLO_MINIMO} caratteri"
            )
        if len(titolo) > TITOLO_MASSIMO:
            raise AnnuncioNonValido(
                f"Il titolo non puo' superare {TITOLO_MASSIMO} caratteri"
            )
        testo = (self.testo or "").strip()
        if not testo:
            raise AnnuncioNonValido("Il testo non puo' essere vuoto")
        if len(testo) > TESTO_MASSIMO:
            raise AnnuncioNonValido(
                f"Il testo non puo' superare {TESTO_MASSIMO} caratteri"
            )
        object.__setattr__(self, "titolo", titolo)
        object.__setattr__(self, "testo", testo)

    @property
    def e_bozza(self) -> bool:
        return not self.pubblicato

    @property
    def data_leggibile(self) -> str:
        """La data come la scriverebbe una persona: '22 agosto 2026, 14:09'."""
        return formatta_data(self.aggiornato_il or self.creato_il)

    @property
    def anteprima(self) -> str:
        """Prima riga utile del testo, per gli elenchi compatti."""
        for riga in self.testo.splitlines():
            pulita = riga.strip().lstrip("#").strip()
            if pulita:
                return pulita[:160] + ("..." if len(pulita) > 160 else "")
        return ""


MESI = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)


def formatta_data(iso: str) -> str:
    """Da ISO a '22 agosto 2026, 14:09'. Se non e' leggibile, torna com'era."""
    if not iso:
        return ""
    try:
        quando = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return str(iso)
    return f"{quando.day} {MESI[quando.month - 1]} {quando.year}, {quando:%H:%M}"


def puo_pubblicare(utente, lega) -> bool:
    """Amministra la lega chi l'ha creata, oppure il presidente.

    Il controllo sta qui e non nella pagina: nascondere un bottone non e' un
    controllo, e `crea_annuncio` lo richiama da sola.
    """
    if utente is None or not getattr(utente, "attivo", True):
        return False
    if lega is not None and getattr(utente, "id", None) == getattr(
        lega, "admin_id", None
    ):
        return True
    return bool(getattr(utente, "e_presidente", False))


def crea_annuncio(
    id_: int,
    lega,
    utente,
    titolo: str,
    testo: str,
    tipo: TipoAnnuncio = TipoAnnuncio.NOTIZIA,
    giornata: int | None = None,
    pubblicato: bool = True,
    in_evidenza: bool = False,
) -> Annuncio:
    """Costruisce un annuncio, rifiutando chi non ha il permesso di scriverlo."""
    if not puo_pubblicare(utente, lega):
        raise NonAutorizzato("Solo chi amministra la lega puo' pubblicare sulla bacheca.")
    adesso = _ora()
    return Annuncio(
        id=id_,
        lega_id=lega.id,
        titolo=titolo,
        testo=testo,
        tipo=tipo,
        autore_id=utente.id,
        autore_nome=utente.nome,
        giornata=giornata,
        pubblicato=pubblicato,
        in_evidenza=in_evidenza,
        creato_il=adesso,
        aggiornato_il=adesso,
    )


def modifica(annuncio: Annuncio, utente, lega, **campi) -> Annuncio:
    """Riscrive un annuncio esistente, aggiornando la data di modifica."""
    if not puo_pubblicare(utente, lega):
        raise NonAutorizzato("Solo chi amministra la lega puo' modificare la bacheca.")
    ammessi = {
        "titolo",
        "testo",
        "tipo",
        "giornata",
        "pubblicato",
        "in_evidenza",
    }
    ignoti = set(campi) - ammessi
    if ignoti:
        raise AnnuncioNonValido(f"Campi non modificabili: {', '.join(sorted(ignoti))}")
    return replace(annuncio, aggiornato_il=_ora(), **campi)


def pubblica(annuncio: Annuncio, utente, lega) -> Annuncio:
    return modifica(annuncio, utente, lega, pubblicato=True)


def ritira(annuncio: Annuncio, utente, lega) -> Annuncio:
    """Riporta un annuncio a bozza: sparisce dalla bacheca ma non si perde."""
    return modifica(annuncio, utente, lega, pubblicato=False)


def _quando(annuncio: Annuncio) -> float:
    """Istante dell'annuncio come numero. 0 se la data e' illeggibile."""
    grezza = annuncio.aggiornato_il or annuncio.creato_il
    try:
        return datetime.fromisoformat(str(grezza).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def ordina(annunci: list[Annuncio]) -> list[Annuncio]:
    """In evidenza prima, poi dal piu' recente al piu' vecchio.

    Le date sono stringhe ISO e non si possono negare: si ordina sul timestamp
    numerico, negato, cosi' l'ordine decrescente sta nella stessa chiave
    crescente del flag «in evidenza». L'id negato rompe i pari merito fra due
    annunci scritti nello stesso secondo.
    """
    return sorted(
        annunci,
        key=lambda a: (0 if a.in_evidenza else 1, -_quando(a), -a.id),
    )


def visibili_per(annunci: list[Annuncio], utente, lega) -> list[Annuncio]:
    """Cosa vede questa persona: i pubblicati, piu' le proprie bozze.

    Le bozze restano visibili a chi amministra, cosi' il recap si puo'
    preparare prima che la giornata sia chiusa.
    """
    lega_id = getattr(lega, "id", None)
    amministra = puo_pubblicare(utente, lega)
    scelti = [a for a in annunci if a.lega_id == lega_id and (a.pubblicato or amministra)]
    return ordina(scelti)


def filtra_per_tipo(annunci: list[Annuncio], tipo: TipoAnnuncio | None) -> list[Annuncio]:
    if tipo is None:
        return annunci
    return [a for a in annunci if a.tipo is tipo]
