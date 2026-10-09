"""Oggetti di dominio di FantaCalcio NuoVo: giocatori, contratti, rose.

Python puro: nessuna dipendenza da Streamlit o dal database, cosi' le regole
restano testabili e riutilizzabili se un domani il sito cambia tecnologia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .identita import IdentitaSquadra
from .regole import RUOLO_PORTIERE, ParametriLega


@dataclass(frozen=True)
class Giocatore:
    """Un calciatore reale. `ingaggio` e' lo stipendio annuo lordo, fonte Capology."""

    id: int
    nome: str
    club: str
    ruoli: tuple[str, ...]
    ingaggio: float
    nazionalita: str = "Italia"
    data_nascita: date | None = None
    # Il ruolo Classic (P/D/C/A) del listone. Non si ricava da quelli Mantra:
    # un esterno «E» in Classic puo' essere difensore o centrocampista, e solo
    # la fonte sa quale dei due. Se non si sa, resta vuoto.
    ruolo_classic: str = ""
    # Dal listone ufficiale: id, quotazione Mantra e valore di mercato.
    # Non concorrono al Salary Cap, che usa gli ingaggi reali di Capology.
    id_ufficiale: int | None = None
    quotazione: float | None = None
    fvm: float | None = None

    @property
    def portiere(self) -> bool:
        return RUOLO_PORTIERE in self.ruoli

    def eta_al(self, giorno: date) -> int | None:
        """Anni compiuti a una certa data. None se la data di nascita manca."""
        if self.data_nascita is None:
            return None
        anni = giorno.year - self.data_nascita.year
        if (giorno.month, giorno.day) < (self.data_nascita.month, self.data_nascita.day):
            anni -= 1
        return anni

    @property
    def italiano(self) -> bool:
        return self.nazionalita.strip().lower() == "italia"

    def under_21(self, data_riferimento: date, parametri: ParametriLega) -> bool:
        """Articolo 2: italiano che non ha 21 anni alla data di riferimento.

        La data e' il **31 agosto** della stagione, fissa tutti gli anni per
        scelta della lega: lo status si cristallizza li' e vale per l'annata.
        Chi compie 21 anni a ottobre resta Under per la stagione in corso.
        Vedi `competizioni.data_riferimento_u21`.
        """
        if self.nazionalita != parametri.nazionalita_u21:
            return False
        eta = self.eta_al(data_riferimento)
        return eta is not None and eta < parametri.eta_limite_u21


@dataclass(frozen=True)
class Contratto:
    """Contratto di un giocatore con una squadra della lega.

    `anni_residui` e' il valore vivo, aggiornato dopo ogni sessione di mercato.
    `prolungato` traccia il Lodo Corti: un giocatore puo' beneficiare del
    prolungamento da scambio una sola volta nella sua permanenza in lega.
    """

    giocatore_id: int
    squadra_id: int
    anni_residui: int
    prolungato: bool = False
    stagione_prolungamento: str | None = None

    @property
    def in_scadenza(self) -> bool:
        """Contratto annuale: quello che conta per la regola "1/3"."""
        return self.anni_residui == 1

    @property
    def anni_oltre_quello_in_corso(self) -> int:
        """Gli anni che resterebbero da pagare **dopo** la stagione in corso.

        E' la base del Dead Money secondo il regolamento V3: l'anno in corso
        si paga comunque, perche' «i salari vengono pagati in anticipo», e
        quindi non entra nella buonuscita.
        """
        return max(self.anni_residui - 1, 0)

    def valore_residuo(self, ingaggio: float) -> float:
        """Ingaggio annuo x anni residui oltre quello in corso.

        E' la base di calcolo del Dead Money (art. 7, Lodo Origi). Contare
        anche l'anno in corso gonfiava la buonuscita di un'annualita': sul
        caso d'esempio del regolamento — ingaggio 10M, contratto di 5 anni,
        svincolo nel primo anno — veniva 25M invece dei 20M scritti li'.
        """
        return ingaggio * self.anni_oltre_quello_in_corso


@dataclass(frozen=True)
class Squadra:
    """Anagrafica di una squadra della lega, identita' visiva compresa."""

    id: int
    nome: str
    presidente: str
    identita: IdentitaSquadra = field(default_factory=IdentitaSquadra)
    # None per le squadre create prima delle leghe multiple (la demo storica).
    lega_id: int | None = None

    @property
    def motto(self) -> str:
        return self.identita.motto

    @property
    def stadio(self) -> str:
        return self.identita.stadio

    @property
    def citta(self) -> str:
        return self.identita.citta

    @property
    def curva(self) -> str:
        return self.identita.curva

    def maglia(self, larghezza: int = 180) -> str:
        return self.identita.maglia(larghezza)


@dataclass(frozen=True)
class VoceDeadMoney:
    """Quel che uno svincolo lascia a carico della squadra (art. 7).

    Sono **due cose distinte**, e il V3 le tiene separate anche nel suo
    esempio: la buonuscita del Lodo Origi (`importo`) e l'ingaggio del
    giocatore andato via, che «continua a pesare sul Salary Cap fino al
    termine della stagione in corso» (`ingaggio_a_carico`).

    Tenerle in un numero solo sarebbe piu' comodo e direbbe una bugia: il
    Dead Money mostrato in tabella diventerebbe piu' grande di quello che la
    regola chiama Dead Money. Dalla stagione successiva non resta niente di
    nessuna delle due.
    """

    giocatore_id: int
    nome_giocatore: str
    importo: float
    stagione: str
    addebitato: bool = False
    ingaggio_a_carico: float = 0.0

    @property
    def totale(self) -> float:
        """Quanto pesa in tutto sul Salary Cap della stagione in corso."""
        return self.importo + self.ingaggio_a_carico


@dataclass
class Rosa:
    """La rosa di una squadra: contratti, dead money e i giocatori collegati."""

    squadra: Squadra
    contratti: list[Contratto] = field(default_factory=list)
    dead_money: list[VoceDeadMoney] = field(default_factory=list)
    # Articolo 8: portiere d'emergenza (Lodo Messina). Non firma contratto e
    # non incide ne' sul monte anni ne' sul Salary Cap.
    portiere_emergenza_id: int | None = None
    # Quali dei suoi portieri la squadra dichiara indisponibili. E' la base su
    # cui si decide se l'emergenza spetta, quindi va conservata: senza, al
    # giro successivo sembrerebbero tornati tutti disponibili.
    portieri_indisponibili: tuple[int, ...] = ()
    # Articolo 2: i posti rosa guadagnati dagli Under 21, **congelati** al
    # ricalcolo annuale. None = non ancora ricalcolato, e allora si contano i
    # giocatori in rosa, che e' quel che serve prima della prima asta.
    slot_u21_congelato: int | None = None

    def __post_init__(self) -> None:
        self._indice: dict[int, Giocatore] = {}

    def collega(self, giocatori: dict[int, Giocatore]) -> Rosa:
        """Associa l'anagrafica dei giocatori: serve per ingaggi, ruoli ed eta'."""
        self._indice = dict(giocatori)
        return self

    def giocatore(self, giocatore_id: int) -> Giocatore:
        try:
            return self._indice[giocatore_id]
        except KeyError:
            raise KeyError(
                f"Giocatore {giocatore_id} non collegato alla rosa "
                f"{self.squadra.nome}: chiama prima Rosa.collega()"
            ) from None

    @property
    def giocatori(self) -> list[Giocatore]:
        return [self.giocatore(c.giocatore_id) for c in self.contratti]

    @property
    def dimensione(self) -> int:
        return len(self.contratti)

    @property
    def portieri(self) -> list[Giocatore]:
        return [g for g in self.giocatori if g.portiere]

    @property
    def anni_impegnati(self) -> int:
        """Somma degli anni di contratto: non puo' eccedere il monte anni."""
        return sum(c.anni_residui for c in self.contratti)

    @property
    def contratti_annuali(self) -> list[Contratto]:
        return [c for c in self.contratti if c.in_scadenza]

    @property
    def monte_ingaggi(self) -> float:
        """Somma degli ingaggi dei soli giocatori in rosa (senza Dead Money)."""
        return sum(self.giocatore(c.giocatore_id).ingaggio for c in self.contratti)

    @property
    def dead_money_totale(self) -> float:
        """Le buonuscite ancora da addebitare (art. 7, Lodo Origi)."""
        return sum(v.importo for v in self.dead_money if not v.addebitato)

    @property
    def ingaggi_degli_svincolati(self) -> float:
        """Gli ingaggi di chi e' stato svincolato in riparazione.

        L'articolo 7 li lascia a carico «fino al termine della stagione in
        corso»: tagliare un giocatore a stagione iniziata **non** restituisce
        il suo ingaggio al Salary Cap, restituisce solo i suoi anni.
        """
        return sum(v.ingaggio_a_carico for v in self.dead_money if not v.addebitato)

    @property
    def spesa_salariale(self) -> float:
        """Sul Salary Cap: ingaggi in rosa piu' cio' che lascia uno svincolo."""
        return self.monte_ingaggi + self.dead_money_totale + self.ingaggi_degli_svincolati

    def u21_in_rosa(self, data_draft: date, parametri: ParametriLega) -> int:
        """Quanti Under 21 italiani ci sono **adesso** in rosa."""
        return sum(1 for g in self.giocatori if g.under_21(data_draft, parametri))

    def slot_u21(self, data_draft: date, parametri: ParametriLega) -> int:
        """Posti rosa aggiuntivi guadagnati dagli Under 21 italiani (art. 2).

        Il numero si «ricalcola una sola volta l'anno, prima dell'asta di
        Settembre, e resta invariato per l'intera stagione: svincoli o
        cessioni di Under 21 in corso d'anno non modificano il limite fino al
        ricalcolo successivo».

        Quindi se il valore e' stato congelato vale quello, anche quando in
        rosa gli Under non ci sono piu': togliere un Under a dicembre non
        restringe la rosa a gennaio, che e' esattamente cio' che il V3 vuole
        evitare. Senza congelamento — prima della prima asta — si contano
        quelli presenti.
        """
        if self.slot_u21_congelato is not None:
            return max(0, min(self.slot_u21_congelato, parametri.slot_u21_massimi))
        return min(self.u21_in_rosa(data_draft, parametri), parametri.slot_u21_massimi)

    def contratto_di(self, giocatore_id: int) -> Contratto | None:
        return next((c for c in self.contratti if c.giocatore_id == giocatore_id), None)

    def prolungamenti_stagione(self, stagione: str) -> int:
        """Quanti giocatori ha prolungato in questa stagione (Lodo Longoni)."""
        return sum(
            1
            for c in self.contratti
            if c.prolungato and c.stagione_prolungamento == stagione
        )

    # -- operazioni ---------------------------------------------------------

    def con_contratto(
        self, contratto: Contratto, giocatore: Giocatore | None = None
    ) -> Rosa:
        """Nuova rosa con un contratto aggiunto o sostituito.

        `giocatore` va passato quando arriva da un'altra squadra: senza la sua
        anagrafica la rosa non saprebbe calcolarne ingaggio, ruolo ed eta'.
        """
        rimanenti = [
            c for c in self.contratti if c.giocatore_id != contratto.giocatore_id
        ]
        indice = dict(self._indice)
        if giocatore is not None:
            indice[giocatore.id] = giocatore
        if contratto.giocatore_id not in indice:
            raise KeyError(
                f"Anagrafica mancante per il giocatore {contratto.giocatore_id}: "
                f"passala a con_contratto() insieme al contratto."
            )

        return Rosa(
            squadra=self.squadra,
            contratti=[*rimanenti, contratto],
            dead_money=list(self.dead_money),
            portiere_emergenza_id=self.portiere_emergenza_id,
            portieri_indisponibili=self.portieri_indisponibili,
            slot_u21_congelato=self.slot_u21_congelato,
        ).collega(indice)

    def senza_giocatore(self, giocatore_id: int) -> Rosa:
        """Nuova rosa senza quel giocatore (il Dead Money va aggiunto a parte)."""
        return Rosa(
            squadra=self.squadra,
            contratti=[c for c in self.contratti if c.giocatore_id != giocatore_id],
            dead_money=list(self.dead_money),
            portiere_emergenza_id=self.portiere_emergenza_id,
            portieri_indisponibili=self.portieri_indisponibili,
            slot_u21_congelato=self.slot_u21_congelato,
        ).collega(self._indice)
