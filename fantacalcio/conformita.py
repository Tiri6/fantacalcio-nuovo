"""Verifica di conformita' di una rosa al regolamento.

Restituisce sempre l'elenco completo delle violazioni, mai un semplice
vero/falso: a un fantallenatore serve sapere *cosa* sistemare e di quanto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from .modelli import Rosa
from .regole import ParametriLega


class Momento(Enum):
    """Quando si controlla: il regolamento non e' vincolante sempre allo stesso modo.

    ASTA_SETTEMBRE e RIPARAZIONE chiudono una sessione di mercato, quindi tutto
    e' vincolante. In STAGIONE gli scambi possono far sforare il Salary Cap
    (articolo 8b): il rientro nei 100M e' imposto solo prima dell'asta
    successiva, quindi lo sforamento resta un avviso.
    """

    ASTA_SETTEMBRE = "asta di Settembre"
    RIPARAZIONE = "asta di riparazione"
    STAGIONE = "stagione in corso"


class Gravita(Enum):
    BLOCCO = "blocco"
    AVVISO = "avviso"


@dataclass(frozen=True)
class Violazione:
    codice: str
    articolo: str
    gravita: Gravita
    messaggio: str
    valore: float | int | None = None
    limite: float | int | None = None

    @property
    def bloccante(self) -> bool:
        return self.gravita is Gravita.BLOCCO


@dataclass(frozen=True)
class StatoRosa:
    """Fotografia della rosa piu' l'esito dei controlli."""

    squadra: str
    dimensione: int
    limite_dimensione: int
    slot_u21: int
    portieri: int
    anni_impegnati: int
    anni_disponibili: int
    contratti_annuali: int
    annuali_richiesti: int
    monte_ingaggi: float
    dead_money: float
    spesa_salariale: float
    limite_cap: float
    violazioni: tuple[Violazione, ...]

    @property
    def conforme(self) -> bool:
        """Conforme = nessuna violazione bloccante. Gli avvisi non fermano nulla."""
        return not any(v.bloccante for v in self.violazioni)

    @property
    def bloccanti(self) -> tuple[Violazione, ...]:
        return tuple(v for v in self.violazioni if v.bloccante)

    @property
    def spazio_salariale(self) -> float:
        """Quanto si puo' ancora spendere prima del Salary Cap."""
        return self.limite_cap - self.spesa_salariale


def _milioni(importo: float) -> str:
    return f"{importo / 1_000_000:.1f}M"


def verifica_rosa(
    rosa: Rosa,
    data_draft: date,
    parametri: ParametriLega | None = None,
    momento: Momento = Momento.STAGIONE,
) -> StatoRosa:
    """Controlla una rosa contro tutti gli articoli del regolamento."""
    parametri = parametri or ParametriLega()
    violazioni: list[Violazione] = []

    slot_u21 = rosa.slot_u21(data_draft, parametri)
    limite_dimensione = parametri.rosa_massimo(slot_u21)
    annuali_richiesti = parametri.minimo_annuali(rosa.dimensione)
    chiude_mercato = momento in (Momento.ASTA_SETTEMBRE, Momento.RIPARAZIONE)

    # --- Articolo 2: dimensione rosa ---------------------------------------
    if rosa.dimensione < parametri.rosa_minimo:
        violazioni.append(
            Violazione(
                "rosa_minima",
                "Art. 2",
                Gravita.BLOCCO if chiude_mercato else Gravita.AVVISO,
                f"Rosa di {rosa.dimensione} giocatori: il minimo e' "
                f"{parametri.rosa_minimo}.",
                rosa.dimensione,
                parametri.rosa_minimo,
            )
        )
    if rosa.dimensione > limite_dimensione:
        dettaglio = f"{parametri.rosa_massimo_base}"
        if slot_u21:
            dettaglio += f" + {slot_u21} da espansione Under 21"
        violazioni.append(
            Violazione(
                "rosa_massima",
                "Art. 2",
                Gravita.BLOCCO,
                f"Rosa di {rosa.dimensione} giocatori: il massimo e' "
                f"{limite_dimensione} ({dettaglio}).",
                rosa.dimensione,
                limite_dimensione,
            )
        )

    # --- Articolo 2: portieri ----------------------------------------------
    portieri = len(rosa.portieri)
    if portieri > parametri.portieri_massimo:
        violazioni.append(
            Violazione(
                "portieri",
                "Art. 2",
                Gravita.BLOCCO,
                f"{portieri} portieri in rosa: il massimo e' "
                f"{parametri.portieri_massimo}.",
                portieri,
                parametri.portieri_massimo,
            )
        )

    # --- Articolo 2: monte anni e durata dei contratti ---------------------
    if rosa.anni_impegnati > parametri.monte_anni:
        violazioni.append(
            Violazione(
                "monte_anni",
                "Art. 2",
                Gravita.BLOCCO,
                f"{rosa.anni_impegnati} anni di contratto impegnati: il monte "
                f"anni e' {parametri.monte_anni}.",
                rosa.anni_impegnati,
                parametri.monte_anni,
            )
        )

    for contratto in rosa.contratti:
        fuori_scala = not (
            parametri.contratto_anni_minimo
            <= contratto.anni_residui
            <= parametri.contratto_anni_massimo
        )
        if fuori_scala:
            nome = rosa.giocatore(contratto.giocatore_id).nome
            violazioni.append(
                Violazione(
                    "durata_contratto",
                    "Art. 2",
                    Gravita.BLOCCO,
                    f"{nome}: contratto di {contratto.anni_residui} anni, ammessi "
                    f"da {parametri.contratto_anni_minimo} a "
                    f"{parametri.contratto_anni_massimo}.",
                    contratto.anni_residui,
                    parametri.contratto_anni_massimo,
                )
            )

    # --- Articolo 2: regola "1/3" ------------------------------------------
    annuali = len(rosa.contratti_annuali)
    if annuali < annuali_richiesti:
        violazioni.append(
            Violazione(
                "regola_un_terzo",
                "Art. 2",
                Gravita.BLOCCO if chiude_mercato else Gravita.AVVISO,
                f"{annuali} contratti annuali su {annuali_richiesti} richiesti per "
                f"una rosa da {rosa.dimensione}.",
                annuali,
                annuali_richiesti,
            )
        )

    # --- Articolo 4: Salary Cap e Salary Floor -----------------------------
    # Il Cap si controlla alla fine di ogni asta; in stagione lo sforamento da
    # scambio e' tollerato e va sanato prima dell'asta di Settembre successiva.
    if rosa.spesa_salariale > parametri.salary_cap:
        eccesso = rosa.spesa_salariale - parametri.salary_cap
        violazioni.append(
            Violazione(
                "salary_cap",
                "Art. 4",
                Gravita.BLOCCO if chiude_mercato else Gravita.AVVISO,
                f"Spesa salariale {_milioni(rosa.spesa_salariale)} contro un tetto "
                f"di {_milioni(parametri.salary_cap)}: eccesso di "
                f"{_milioni(eccesso)}.",
                rosa.spesa_salariale,
                parametri.salary_cap,
            )
        )

    # Il Floor si verifica alla fine di ogni sessione d'asta e non conta il
    # Dead Money: la soglia va raggiunta con gli ingaggi dei giocatori in rosa.
    sotto_il_floor = rosa.monte_ingaggi < parametri.salary_floor
    if parametri.salary_floor_attivo and chiude_mercato and sotto_il_floor:
        mancante = parametri.salary_floor - rosa.monte_ingaggi
        violazioni.append(
            Violazione(
                "salary_floor",
                "Art. 4",
                Gravita.BLOCCO,
                f"Ingaggi in rosa {_milioni(rosa.monte_ingaggi)} sotto la soglia "
                f"minima di {_milioni(parametri.salary_floor)}: mancano "
                f"{_milioni(mancante)} (il Dead Money non conta).",
                rosa.monte_ingaggi,
                parametri.salary_floor,
            )
        )

    return StatoRosa(
        squadra=rosa.squadra.nome,
        dimensione=rosa.dimensione,
        limite_dimensione=limite_dimensione,
        slot_u21=slot_u21,
        portieri=portieri,
        anni_impegnati=rosa.anni_impegnati,
        anni_disponibili=parametri.monte_anni - rosa.anni_impegnati,
        contratti_annuali=annuali,
        annuali_richiesti=annuali_richiesti,
        monte_ingaggi=rosa.monte_ingaggi,
        dead_money=rosa.dead_money_totale,
        spesa_salariale=rosa.spesa_salariale,
        limite_cap=parametri.salary_cap,
        violazioni=tuple(violazioni),
    )
