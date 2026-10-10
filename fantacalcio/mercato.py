"""Articoli 5, 6, 7 e 8: finestre di mercato, svincoli e scambi.

Le regole di scambio sono quelle piu' delicate del regolamento, perche' tre
lodi diversi si sovrappongono (Bono, Corti, Longoni). Qui ciascuno e' un
controllo separato, cosi' quando la lega ne emenda uno si tocca una riga sola.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum

from .autenticazione import Utente
from .conformita import Gravita, Momento, Violazione
from .modelli import Contratto, Rosa, VoceDeadMoney
from .regole import CalendarioStagione, ParametriLega


class Finestra(Enum):
    SETTEMBRE = "Asta di Settembre"
    INVERNALE = "Finestra invernale"
    PRIMAVERILE = "Finestra primaverile"


@dataclass(frozen=True)
class StatoMercato:
    """Quali finestre si sono gia' aperte e se il mercato e' ormai chiuso.

    Il regolamento fissa quando ogni finestra *apre* (dopo la 9a e dopo la 18a
    giornata) ma non per quanto resti aperta: la chiusura coincide di fatto
    con lo svolgimento del draft di riparazione. Vedi PUNTI_APERTI.md.
    """

    giornate_disputate: int
    finestre_aperte: tuple[Finestra, ...]
    finestra_piu_recente: Finestra | None
    trade_deadline_superata: bool


def stato_mercato(
    giornate_disputate: int, calendario: CalendarioStagione
) -> StatoMercato:
    """Articolo 5: le finestre seguono i gironcini da 9 partite."""
    aperte: list[Finestra] = [Finestra.SETTEMBRE]
    sequenza = (Finestra.INVERNALE, Finestra.PRIMAVERILE)

    for finestra, giornata_apertura in zip(
        sequenza, calendario.giornate_apertura_finestre, strict=False
    ):
        if giornate_disputate >= giornata_apertura:
            aperte.append(finestra)

    ultima_apertura = (
        calendario.giornate_apertura_finestre[-1]
        if calendario.giornate_apertura_finestre
        else 0
    )
    return StatoMercato(
        giornate_disputate=giornate_disputate,
        finestre_aperte=tuple(aperte),
        finestra_piu_recente=aperte[-1],
        # Dopo la chiusura della finestra primaverile il mercato e' bloccato
        # fino a fine stagione (articolo 5).
        trade_deadline_superata=giornate_disputate > ultima_apertura,
    )


# ---------------------------------------------------------------------------
# Articolo 7: svincoli
# ---------------------------------------------------------------------------


class SvincoloNonAmmesso(Exception):
    """Lo svincolo non e' consentito a questo utente, o su questo giocatore."""


def verifica_svincolo(utente: Utente, rosa: Rosa, giocatore_id: int) -> None:
    """Chi puo' svincolare chi. Solleva invece di restituire un booleano.

    Sta qui e non nella pagina perche' nascondere un bottone non e' un
    controllo: chi arrivasse alla scrittura per un'altra strada — un rerun a
    meta', una sessione riaperta con un ruolo diverso — deve trovare comunque
    la porta chiusa.
    """
    if not utente.puo_svincolare:
        raise SvincoloNonAmmesso(
            f"{utente.nome} non puo' svincolare: serve il presidente della lega."
        )
    if rosa.contratto_di(giocatore_id) is None:
        raise SvincoloNonAmmesso(
            f"{rosa.squadra.nome} non ha in rosa il giocatore {giocatore_id}."
        )


def calcola_dead_money(
    contratto: Contratto, ingaggio: float, parametri: ParametriLega | None = None
) -> float:
    """Lodo Origi: meta' degli anni residui **oltre quello in corso**, per ingaggio.

    Non comprende l'ingaggio della stagione in corso, che resta a carico a
    parte: vedi `VoceDeadMoney` e l'esempio dell'articolo 7.
    """
    parametri = parametri or ParametriLega()
    return round(parametri.quota_dead_money * contratto.valore_residuo(ingaggio), 2)


def svincola(
    rosa: Rosa,
    giocatore_id: int,
    stagione: str,
    parametri: ParametriLega | None = None,
    momento: Momento = Momento.RIPARAZIONE,
) -> tuple[Rosa, VoceDeadMoney | None]:
    """Taglia un giocatore. Cosa lascia dietro dipende da **quando** lo tagli.

    Gli anni si liberano sempre e subito: e' l'effetto sul monte anni, e
    l'articolo 7 non lo lega a nessuna sessione.

    Sul Salary Cap invece il V3 e' netto: «gli effetti sul Salary Cap si
    producono esclusivamente per gli svincoli effettuati nei mercati di
    riparazione in corso di stagione; gli svincoli effettuati prima dell'asta
    di Settembre non hanno alcun effetto sul Salary Cap».

    - **Prima dell'asta di Settembre** (`Momento.ASTA_SETTEMBRE`): niente
      buonuscita e niente ingaggio a carico. Si torna `None` invece di una
      voce da zero, cosi' chi scrive sul database non registra un debito
      inesistente.
    - **In riparazione** (il caso normale): buonuscita del Lodo Origi **piu'**
      l'ingaggio, che resta a carico fino a fine stagione. Dalla stagione
      successiva non pesa piu' niente.
    """
    parametri = parametri or ParametriLega()
    contratto = rosa.contratto_di(giocatore_id)
    if contratto is None:
        raise ValueError(
            f"{rosa.squadra.nome} non ha in rosa il giocatore {giocatore_id}"
        )

    giocatore = rosa.giocatore(giocatore_id)
    nuova = rosa.senza_giocatore(giocatore_id)

    if momento is Momento.ASTA_SETTEMBRE:
        nuova.dead_money = list(rosa.dead_money)
        return nuova, None

    voce = VoceDeadMoney(
        giocatore_id=giocatore_id,
        nome_giocatore=giocatore.nome,
        importo=calcola_dead_money(contratto, giocatore.ingaggio, parametri),
        stagione=stagione,
        ingaggio_a_carico=giocatore.ingaggio,
    )
    nuova.dead_money = [*rosa.dead_money, voce]
    return nuova, voce


# ---------------------------------------------------------------------------
# Articolo 8: scambi
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PropostaScambio:
    """Uno scambio tra due squadre, con eventuali prolungamenti contrattuali.

    `prolungamenti` mappa giocatore_id -> nuova durata residua. Il giocatore si
    scambia insieme alla durata residua del contratto: senza prolungamento la
    durata viaggia invariata.
    """

    da_squadra_a: tuple[int, ...] = ()
    da_squadra_b: tuple[int, ...] = ()
    prolungamenti: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Movimento:
    """Un giocatore che cambia squadra dentro uno scambio."""

    giocatore_id: int
    nome: str
    origine: Rosa
    destinazione: Rosa
    anni_attuali: int
    nuovi_anni: int
    contratto: Contratto

    @property
    def prolungato(self) -> bool:
        return self.nuovi_anni > self.anni_attuali

    @property
    def durata_ridotta(self) -> bool:
        return self.nuovi_anni < self.anni_attuali


def _movimenti(rosa_a: Rosa, rosa_b: Rosa, proposta: PropostaScambio) -> list[Movimento]:
    """Espande la proposta in un movimento per giocatore, con le durate.

    Solleva ValueError se un giocatore non e' nella rosa che dovrebbe cederlo.
    """
    movimenti: list[Movimento] = []
    for giocatori, origine, destinazione in (
        (proposta.da_squadra_a, rosa_a, rosa_b),
        (proposta.da_squadra_b, rosa_b, rosa_a),
    ):
        for giocatore_id in giocatori:
            contratto = origine.contratto_di(giocatore_id)
            if contratto is None:
                raise ValueError(
                    f"{origine.squadra.nome} non ha in rosa il giocatore {giocatore_id}"
                )
            movimenti.append(
                Movimento(
                    giocatore_id=giocatore_id,
                    nome=origine.giocatore(giocatore_id).nome,
                    origine=origine,
                    destinazione=destinazione,
                    anni_attuali=contratto.anni_residui,
                    nuovi_anni=proposta.prolungamenti.get(
                        giocatore_id, contratto.anni_residui
                    ),
                    contratto=contratto,
                )
            )
    return movimenti


def applica_scambio(
    rosa_a: Rosa, rosa_b: Rosa, proposta: PropostaScambio, stagione: str
) -> tuple[Rosa, Rosa]:
    """Restituisce le due rose come sarebbero a scambio ratificato."""
    movimenti = _movimenti(rosa_a, rosa_b, proposta)
    nuova_a, nuova_b = rosa_a, rosa_b

    for movimento in movimenti:
        cede, riceve = (
            (nuova_a, nuova_b)
            if movimento.origine.squadra.id == rosa_a.squadra.id
            else (nuova_b, nuova_a)
        )
        nuovo_contratto = replace(
            movimento.contratto,
            squadra_id=riceve.squadra.id,
            anni_residui=movimento.nuovi_anni,
            prolungato=movimento.contratto.prolungato or movimento.prolungato,
            stagione_prolungamento=(
                stagione
                if movimento.prolungato
                else movimento.contratto.stagione_prolungamento
            ),
        )
        anagrafica = movimento.origine.giocatore(movimento.giocatore_id)
        cede = cede.senza_giocatore(movimento.giocatore_id)
        riceve = riceve.con_contratto(nuovo_contratto, anagrafica)

        if movimento.origine.squadra.id == rosa_a.squadra.id:
            nuova_a, nuova_b = cede, riceve
        else:
            nuova_b, nuova_a = cede, riceve

    return nuova_a, nuova_b


def valida_scambio(
    rosa_a: Rosa,
    rosa_b: Rosa,
    proposta: PropostaScambio,
    stagione: str,
    parametri: ParametriLega | None = None,
) -> list[Violazione]:
    """Controlla lo scambio contro l'articolo 8 e i lodi collegati."""
    parametri = parametri or ParametriLega()

    if not proposta.da_squadra_a and not proposta.da_squadra_b:
        return [
            Violazione(
                "scambio_vuoto",
                "Art. 8",
                Gravita.BLOCCO,
                "Lo scambio non muove nessun giocatore.",
            )
        ]

    try:
        movimenti = _movimenti(rosa_a, rosa_b, proposta)
    except ValueError as errore:
        return [Violazione("scambio_impossibile", "Art. 8", Gravita.BLOCCO, str(errore))]

    violazioni: list[Violazione] = []
    coinvolti = {m.giocatore_id for m in movimenti}

    # Articolo 8, V3: «il contratto si trasferisce con ingaggio e anni residui
    # invariati: non sono ammessi prolungamenti ne' riduzioni di durata, ne' in
    # sede di scambio ne' con altra operazione». Il divieto viene prima di
    # tutto il resto: se cambiare durata non si puo', non ha senso controllare
    # quante volte si puo' farlo.
    if not parametri.prolungamenti_ammessi:
        for movimento in movimenti:
            if movimento.prolungato or movimento.durata_ridotta:
                violazioni.append(
                    Violazione(
                        "durata_invariata",
                        "Art. 8",
                        Gravita.BLOCCO,
                        f"{movimento.nome}: il contratto si trasferisce com'e', "
                        f"{movimento.anni_attuali} anni. Prolungamenti e "
                        f"riduzioni di durata non sono ammessi.",
                        movimento.nuovi_anni,
                        movimento.anni_attuali,
                    )
                )

    for giocatore_id in proposta.prolungamenti:
        if giocatore_id not in coinvolti:
            violazioni.append(
                Violazione(
                    "prolungamento_estraneo",
                    "Art. 8",
                    Gravita.BLOCCO,
                    f"Prolungamento richiesto per il giocatore {giocatore_id}, "
                    f"che non fa parte dello scambio.",
                )
            )

    # I lodi Bono, Corti e Longoni regolavano **come** si prolunga: col V3 non
    # si prolunga affatto, e il divieto qui sopra li assorbe tutti. Restano
    # scritti e provati per il giorno in cui un lodo riaprisse la strada.
    con_durata_variabile = movimenti if parametri.prolungamenti_ammessi else []

    for movimento in con_durata_variabile:
        # Lodo Bono: mai ridurre la durata contrattuale.
        if movimento.durata_ridotta:
            violazioni.append(
                Violazione(
                    "lodo_bono",
                    "Art. 8 - Lodo Bono",
                    Gravita.BLOCCO,
                    f"{movimento.nome}: la durata non puo' scendere da "
                    f"{movimento.anni_attuali} a {movimento.nuovi_anni} anni.",
                    movimento.nuovi_anni,
                    movimento.anni_attuali,
                )
            )
            continue

        if not movimento.prolungato:
            continue

        # Lodo Corti: un solo prolungamento per giocatore in tutta la permanenza.
        if movimento.contratto.prolungato:
            violazioni.append(
                Violazione(
                    "lodo_corti",
                    "Art. 8 - Lodo Corti",
                    Gravita.BLOCCO,
                    f"{movimento.nome} ha gia' beneficiato di un prolungamento da "
                    f"scambio: deve arrivare a scadenza naturale e rientrare in "
                    f"draft list.",
                )
            )

        if movimento.nuovi_anni > parametri.contratto_anni_massimo:
            violazioni.append(
                Violazione(
                    "durata_contratto",
                    "Art. 2",
                    Gravita.BLOCCO,
                    f"{movimento.nome}: {movimento.nuovi_anni} anni superano il "
                    f"massimo di {parametri.contratto_anni_massimo}.",
                    movimento.nuovi_anni,
                    parametri.contratto_anni_massimo,
                )
            )

    # Lodo Longoni: massimo 2 giocatori prolungati per squadra per stagione.
    # Il prolungamento e' un beneficio di chi riceve il giocatore, quindi si
    # conta sulla squadra di destinazione.
    limite = parametri.prolungamenti_per_squadra_a_stagione
    squadre_da_contare = (rosa_a, rosa_b) if parametri.prolungamenti_ammessi else ()
    for rosa in squadre_da_contare:
        nuovi = sum(
            1
            for m in movimenti
            if m.prolungato and m.destinazione.squadra.id == rosa.squadra.id
        )
        totale = rosa.prolungamenti_stagione(stagione) + nuovi
        if totale > limite:
            violazioni.append(
                Violazione(
                    "lodo_longoni",
                    "Art. 6 - Lodo Longoni",
                    Gravita.BLOCCO,
                    f"{rosa.squadra.nome}: {totale} prolungamenti nella stagione "
                    f"{stagione}, il massimo e' {limite}.",
                    totale,
                    limite,
                )
            )

    # Effetti sulle rose risultanti: monte anni e Salary Cap.
    nuova_a, nuova_b = applica_scambio(rosa_a, rosa_b, proposta, stagione)

    for rosa in (nuova_a, nuova_b):
        if rosa.anni_impegnati > parametri.monte_anni:
            violazioni.append(
                Violazione(
                    "monte_anni",
                    "Art. 8a",
                    Gravita.BLOCCO,
                    f"{rosa.squadra.nome}: lo scambio porta a "
                    f"{rosa.anni_impegnati} anni impegnati, oltre il monte anni "
                    f"di {parametri.monte_anni}.",
                    rosa.anni_impegnati,
                    parametri.monte_anni,
                )
            )
        # Articolo 8b: in stagione il Salary Cap non blocca lo scambio, ma il
        # rientro nei 100M sara' imposto prima dell'asta di Settembre.
        if rosa.spesa_salariale > parametri.salary_cap:
            eccesso = rosa.spesa_salariale - parametri.salary_cap
            violazioni.append(
                Violazione(
                    "salary_cap",
                    "Art. 8b",
                    Gravita.AVVISO,
                    f"{rosa.squadra.nome} sfora il Salary Cap di "
                    f"{eccesso / 1_000_000:.1f}M: ammesso in stagione, da sanare "
                    f"prima dell'asta di Settembre.",
                    rosa.spesa_salariale,
                    parametri.salary_cap,
                )
            )

    return violazioni


def scambio_ratificabile(
    comunicazione: datetime,
    inizio_giornata: datetime,
    parametri: ParametriLega | None = None,
) -> bool:
    """Articolo 8: va comunicato almeno 24 ore prima dell'inizio della giornata.

    Se arriva oltre il termine lo scambio non e' nullo: semplicemente non vale
    per la giornata imminente e ha effetto da quella successiva.
    """
    parametri = parametri or ParametriLega()
    anticipo = inizio_giornata - comunicazione
    return anticipo >= timedelta(hours=parametri.ore_ratifica_scambio)
