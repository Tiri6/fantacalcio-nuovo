"""La sala del draft: chi chiama, quando, e cosa succede a chi chiama.

Dall'anno prossimo il draft non si fa piu' su un foglio: dieci persone entrano
qui dentro e chiamano a turno. Ci sono due tipi di sala — quella di inizio
stagione e quelle dei mercati di riparazione — e cambiano in una cosa sola:
l'ordine di chiamata. Il resto e' identico.

**L'ordine si congela all'apertura.** La sala non ricalcola di chi e' il turno
a ogni richiesta: si fa l'elenco completo delle chiamate quando la sala apre e
non si tocca piu'. Non e' un'ottimizzazione — l'ordine dei round di
riparazione dipende dalla classifica, e una giornata calcolata a sala aperta
riordinerebbe i turni a meta' draft, facendo chiamare due volte chi aveva gia'
chiamato. E' la stessa ragione per cui lo slot Under 21 si congela al 31
agosto.

**Il registro delle chiamate e' in sola aggiunta.** Di chi sia il turno si
ricava contando quante chiamate sono state fatte, non da un campo «turno
corrente» che qualcuno deve ricordarsi di aggiornare: cosi' non esiste lo
stato incoerente in cui il contatore dice una cosa e le chiamate un'altra, e
due persone che chiamano nello stesso istante non possono prendere lo stesso
numero.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum

from .conformita import Gravita, Momento, Violazione, verifica_rosa
from .draft import ordine_riparazione, ordine_round
from .modelli import Giocatore, Rosa
from .regole import ParametriLega


class TipoSala(Enum):
    """Le due sale, che differiscono solo nell'ordine di chiamata."""

    SETTEMBRE = ("Draft di Settembre", Momento.ASTA_SETTEMBRE)
    RIPARAZIONE = ("Mercato di riparazione", Momento.RIPARAZIONE)

    def __init__(self, etichetta: str, momento_di_chiusura: Momento):
        self.etichetta = etichetta
        # Quando la sala chiude, la rosa si valuta con questo momento: li' i
        # minimi tornano vincolanti, perche' la rosa non si sta piu' costruendo.
        self.momento_di_chiusura = momento_di_chiusura


class StatoSala(Enum):
    APERTA = "aperta"
    IN_CORSO = "in corso"
    CHIUSA = "chiusa"


class SalaNonAmmessa(RuntimeError):
    """Una transizione o una chiamata che la sala non consente."""


@dataclass(frozen=True)
class Scelta:
    """Una chiamata gia' fatta: chi ha preso chi, e per quanti anni."""

    numero: int
    squadra_id: int
    giocatore_id: int
    anni: int
    quando: str = ""


@dataclass(frozen=True)
class Turno:
    """Di chi e' la chiamata, e che chiamata e'."""

    numero: int
    squadra_id: int
    round: int
    posizione: int
    scade_il: datetime | None = None

    @property
    def etichetta(self) -> str:
        return f"Round {self.round} · chiamata {self.posizione}"


@dataclass(frozen=True)
class Sala:
    """Una sala del draft, con l'ordine di chiamata gia' congelato."""

    id: int
    lega_id: int | None
    tipo: TipoSala
    stato: StatoSala
    stagione: str
    # Una squadra per chiamata, dalla prima all'ultima. La lunghezza dice
    # quante chiamate ha la sala: non serve un campo «round totali» che possa
    # contraddirla.
    chiamate_previste: tuple[int, ...] = ()
    # Quanto dura un turno. A None non scade: il draft si fa insieme, e un
    # timer che passa il turno mentre qualcuno sta ancora decidendo e' peggio
    # di un draft lento.
    secondi_per_chiamata: int | None = None
    aperta_il: str = ""
    cominciata_il: str = ""
    chiusa_il: str = ""
    squadre: tuple[int, ...] = field(default_factory=tuple)

    @property
    def chiamate_totali(self) -> int:
        return len(self.chiamate_previste)

    @property
    def round_totali(self) -> int:
        quante = len(self.squadre)
        return self.chiamate_totali // quante if quante else 0


# ---------------------------------------------------------------------------
# Comporre l'ordine
# ---------------------------------------------------------------------------


def componi_chiamate(
    tipo: TipoSala,
    round_totali: int,
    ordine_lottery: Sequence[int],
    classifica: Sequence[int],
) -> tuple[int, ...]:
    """L'elenco completo delle chiamate, una squadra per volta.

    Settembre segue la Lottery, tranne i round multipli di 3 che seguono la
    classifica dell'anno prima (art. 3). La riparazione segue l'ordine inverso
    di classifica, in tutti i round.

    `classifica` va dalla prima all'ultima. Serve a tutte e due: a Settembre
    per i round multipli di 3, in riparazione per girarla.
    """
    if round_totali < 1:
        raise ValueError(f"Servono almeno un round, ricevuti {round_totali}")
    if not ordine_lottery and not classifica:
        raise ValueError("Serve l'ordine di almeno una squadra")

    chiamate: list[int] = []
    for numero in range(1, round_totali + 1):
        if tipo is TipoSala.RIPARAZIONE:
            chiamate.extend(ordine_riparazione(classifica))
        else:
            chiamate.extend(ordine_round(numero, ordine_lottery, classifica))
    return tuple(chiamate)


def apri(
    id_: int,
    lega_id: int | None,
    tipo: TipoSala,
    stagione: str,
    round_totali: int,
    ordine_lottery: Sequence[int],
    classifica: Sequence[int],
    secondi_per_chiamata: int | None = None,
    adesso: datetime | None = None,
) -> Sala:
    """Apre una sala e le congela l'ordine di chiamata."""
    adesso = adesso or datetime.now()
    chiamate = componi_chiamate(tipo, round_totali, ordine_lottery, classifica)
    return Sala(
        id=id_,
        lega_id=lega_id,
        tipo=tipo,
        stato=StatoSala.APERTA,
        stagione=stagione,
        chiamate_previste=chiamate,
        secondi_per_chiamata=secondi_per_chiamata,
        aperta_il=adesso.isoformat(timespec="seconds"),
        squadre=tuple(dict.fromkeys(chiamate)),
    )


def comincia(sala: Sala, adesso: datetime | None = None) -> Sala:
    """Da «aperta» a «in corso»: da qui si chiama."""
    if sala.stato is not StatoSala.APERTA:
        raise SalaNonAmmessa(
            f"La sala e' {sala.stato.value}: si comincia solo da una sala aperta."
        )
    adesso = adesso or datetime.now()
    return replace(
        sala,
        stato=StatoSala.IN_CORSO,
        cominciata_il=adesso.isoformat(timespec="seconds"),
    )


def chiudi(sala: Sala, adesso: datetime | None = None) -> Sala:
    """Chiude la sala. Da qui gli anni si correggono, ma non si chiama piu'."""
    if sala.stato is StatoSala.CHIUSA:
        raise SalaNonAmmessa("La sala e' gia' chiusa.")
    adesso = adesso or datetime.now()
    return replace(
        sala, stato=StatoSala.CHIUSA, chiusa_il=adesso.isoformat(timespec="seconds")
    )


# ---------------------------------------------------------------------------
# Di chi e' il turno
# ---------------------------------------------------------------------------


def turno(sala: Sala, scelte: Sequence[Scelta]) -> Turno | None:
    """La chiamata che tocca adesso, o `None` se la sala ha finito.

    Si conta: fatte N chiamate, tocca la N+1. Nessun campo «turno corrente» da
    tenere allineato, quindi nessuno stato che possa contraddire il registro.
    """
    fatte = len(scelte)
    if sala.stato is not StatoSala.IN_CORSO or fatte >= sala.chiamate_totali:
        return None

    quante = len(sala.squadre) or 1
    scadenza = None
    if sala.secondi_per_chiamata:
        partenza = _ultimo_istante(sala, scelte)
        if partenza is not None:
            scadenza = partenza + timedelta(seconds=sala.secondi_per_chiamata)

    return Turno(
        numero=fatte + 1,
        squadra_id=sala.chiamate_previste[fatte],
        round=fatte // quante + 1,
        posizione=fatte % quante + 1,
        scade_il=scadenza,
    )


def _ultimo_istante(sala: Sala, scelte: Sequence[Scelta]) -> datetime | None:
    """Da quando scorre il turno: l'ultima chiamata, o l'inizio della sala."""
    grezzo = scelte[-1].quando if scelte else sala.cominciata_il
    if not grezzo:
        return None
    try:
        return datetime.fromisoformat(str(grezzo).replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Chiamare
# ---------------------------------------------------------------------------


def verifica_chiamata(
    sala: Sala,
    scelte: Sequence[Scelta],
    squadra_id: int,
    giocatore: Giocatore,
    anni: int,
    rosa: Rosa,
    disponibili: set[int],
    parametri: ParametriLega | None = None,
    data_draft=None,
) -> list[Violazione]:
    """Tutto quel che non va in questa chiamata. Vuoto = si puo' chiamare.

    Torna violazioni e non un booleano, come ogni altro controllo del progetto:
    chi chiama deve sapere **di quanto** sfora, non solo che sfora — davanti a
    dieci persone che aspettano, «monte anni superato» senza il numero e'
    inutile quanto il silenzio.
    """
    parametri = parametri or ParametriLega()
    violazioni: list[Violazione] = []

    if sala.stato is not StatoSala.IN_CORSO:
        violazioni.append(
            Violazione(
                "sala_chiusa",
                "Art. 3",
                Gravita.BLOCCO,
                f"La sala e' {sala.stato.value}: non si chiama.",
            )
        )
        return violazioni

    atteso = turno(sala, scelte)
    if atteso is None:
        violazioni.append(
            Violazione(
                "sala_finita",
                "Art. 3",
                Gravita.BLOCCO,
                "Le chiamate di questa sala sono finite.",
            )
        )
        return violazioni

    if atteso.squadra_id != squadra_id:
        violazioni.append(
            Violazione(
                "non_e_il_tuo_turno",
                "Art. 3",
                Gravita.BLOCCO,
                f"Non e' il tuo turno: tocca alla chiamata {atteso.numero}, "
                f"{atteso.etichetta}.",
                squadra_id,
                atteso.squadra_id,
            )
        )

    gia_chiamati = {s.giocatore_id for s in scelte}
    if giocatore.id in gia_chiamati:
        violazioni.append(
            Violazione(
                "gia_chiamato",
                "Art. 6",
                Gravita.BLOCCO,
                f"{giocatore.nome} e' gia' stato chiamato in questa sala.",
            )
        )
    elif giocatore.id not in disponibili:
        violazioni.append(
            Violazione(
                "non_disponibile",
                "Art. 6",
                Gravita.BLOCCO,
                f"{giocatore.nome} non e' libero: un giocatore puo' stare in "
                f"una sola rosa.",
            )
        )

    if not (parametri.contratto_anni_minimo <= anni <= parametri.contratto_anni_massimo):
        violazioni.append(
            Violazione(
                "durata_contratto",
                "Art. 2",
                Gravita.BLOCCO,
                f"Contratto di {anni} anni: ammessi da "
                f"{parametri.contratto_anni_minimo} a "
                f"{parametri.contratto_anni_massimo}.",
                anni,
                parametri.contratto_anni_massimo,
            )
        )
        return violazioni + _dopo_la_chiamata(
            rosa, giocatore, anni, parametri, data_draft, salta=True
        )

    violazioni += _dopo_la_chiamata(rosa, giocatore, anni, parametri, data_draft)
    return violazioni


def _dopo_la_chiamata(
    rosa: Rosa,
    giocatore: Giocatore,
    anni: int,
    parametri: ParametriLega,
    data_draft,
    salta: bool = False,
) -> list[Violazione]:
    """Come sarebbe la rosa con questo giocatore dentro, e cosa si romperebbe.

    Si guarda con `Momento.DRAFT`: i tetti bloccano — rosa, portieri, monte
    anni, Salary Cap — e i minimi no. Alla terza chiamata la rosa e' corta per
    definizione: se il minimo bloccasse, nessuno arriverebbe alla quarta.
    """
    if salta or data_draft is None:
        return []
    futura = rosa.con_giocatore(giocatore, anni)
    stato = verifica_rosa(futura, data_draft, parametri, Momento.DRAFT)
    return [v for v in stato.violazioni if v.bloccante]


def registra(
    sala: Sala,
    scelte: Sequence[Scelta],
    squadra_id: int,
    giocatore_id: int,
    anni: int,
    adesso: datetime | None = None,
) -> Scelta:
    """La chiamata da scrivere nel registro.

    Il numero lo decide il registro, non chi chiama: e' quello che impedisce a
    due persone che premono insieme di prendere lo stesso posto, perche' il
    numero e' unico nella tabella e la seconda scrittura viene rifiutata.
    """
    adesso = adesso or datetime.now()
    return Scelta(
        numero=len(scelte) + 1,
        squadra_id=squadra_id,
        giocatore_id=giocatore_id,
        anni=anni,
        quando=adesso.isoformat(timespec="seconds"),
    )


def scelte_di(scelte: Sequence[Scelta], squadra_id: int) -> list[Scelta]:
    """Cosa ha preso una squadra in questa sala.

    Serve alla finestra di correzione degli anni: si correggono **solo** i
    giocatori presi qui, non la rosa intera.
    """
    return [s for s in scelte if s.squadra_id == squadra_id]
