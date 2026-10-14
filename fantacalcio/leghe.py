"""Una lega: chi la amministra, chi ci gioca, con quali regole si gioca.

Fino a qui il progetto assumeva una lega sola, cablata nei parametri. Questo
modulo introduce l'oggetto `Lega`, il codice d'invito che permette a un amico
di entrarci e le `OpzioniLega`, cioe' tutte le scelte che su Leghe Fantacalcio
si fanno in fase di creazione: modalita', moduli, bonus, modificatori, fasce.

Le opzioni si conservano come JSON in una colonna sola invece che come colonne
separate. E' una scelta: le opzioni cambiano spesso (ogni stagione la
piattaforma ne aggiunge), e una migrazione di schema per ogni nuova casella
sarebbe un costo continuo. Le regole *vincolanti* del regolamento restano
invece in `ParametriLega`, tipizzate.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum

from .competizioni import (
    CriterioF1Rush,
    FormatoCoppa,
    RegoleCoppa,
    RegoleF1Rush,
    TipoCompetizione,
)
from .regole import ParametriLega

# --- Codice d'invito --------------------------------------------------------
#
# Alfabeto senza caratteri che si confondono quando il codice viene letto ad
# alta voce o ricopiato da uno screenshot: niente O/0, I/1, L, U/V.
ALFABETO_CODICE = "ABCDEFGHJKMNPQRSTWXYZ23456789"
LUNGHEZZA_CODICE = 8
FORMATO_CODICE = re.compile(r"^[A-Z0-9]{4}-?[A-Z0-9]{4}$")


class CodiceNonValido(ValueError):
    pass


class LegaNonValida(ValueError):
    pass


def genera_codice_invito() -> str:
    """Codice a otto caratteri, scritto come XXXX-XXXX perche' si ricopi meglio."""
    grezzo = "".join(secrets.choice(ALFABETO_CODICE) for _ in range(LUNGHEZZA_CODICE))
    return f"{grezzo[:4]}-{grezzo[4:]}"


def normalizza_codice(valore: str) -> str:
    """Accetta 'abcd1234', 'ABCD-1234', ' abcd 1234 ' e restituisce 'ABCD-1234'."""
    if not isinstance(valore, str) or not valore.strip():
        raise CodiceNonValido("Il codice d'invito non puo' essere vuoto")
    pulito = re.sub(r"[\s-]", "", valore).upper()
    if len(pulito) != LUNGHEZZA_CODICE or not pulito.isalnum():
        raise CodiceNonValido(
            f"Il codice d'invito deve avere {LUNGHEZZA_CODICE} caratteri "
            f"(hai scritto '{valore}')"
        )
    return f"{pulito[:4]}-{pulito[4:]}"


# --- Email ------------------------------------------------------------------
#
# Validazione deliberatamente permissiva: serve a intercettare i refusi, non a
# decidere se un indirizzo esiste. L'unica prova che un'email e' valida e'
# scriverci.
FORMATO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class EmailNonValida(ValueError):
    pass


def normalizza_email(valore: str) -> str:
    if not isinstance(valore, str) or not valore.strip():
        raise EmailNonValida("L'indirizzo email non puo' essere vuoto")
    pulito = valore.strip().lower()
    if not FORMATO_EMAIL.match(pulito):
        raise EmailNonValida(f"'{valore}' non sembra un indirizzo email")
    return pulito


# --- Opzioni di gioco -------------------------------------------------------


class Modalita(Enum):
    CLASSIC = "Classic"
    MANTRA = "Mantra"

    @property
    def etichetta(self) -> str:
        return self.value


class TipoAsta(Enum):
    CHIAMATA = "Asta a chiamata"
    RANDOM = "Asta con ordine casuale"
    BUSTA_CHIUSA = "Offerta a busta chiusa"
    DRAFT = "Draft (fuori piattaforma)"

    @property
    def etichetta(self) -> str:
        return self.value


class FormatoCampionato(Enum):
    ANDATA_RITORNO = "Andata e ritorno"
    SOLO_ANDATA = "Solo andata"
    GIRONE_TRIPLO = "Girone triplo"

    @property
    def etichetta(self) -> str:
        return self.value


class ModalitaSostituzioni(Enum):
    """Come il sistema rimpiazza chi resta senza voto (regole Mantra).

    Le tre modalita' sono quelle della piattaforma. Cambiano *l'ordine delle
    priorita'*, non il numero di sostituzioni:

    - **Easy** — non si tocca niente: entra solo chi puo' occupare quel posto
      per ruolo, e nessuno gioca mai fuori posizione. Il modulo resta quello.
    - **Basic** — prima si prova a tenere in piedi lo schema senza adattare
      nessuno; se non si puo', entra chi c'e' e paga il malus. E' il default
      della piattaforma.
    - **Master** — comanda l'ordine della panchina: entra il primo che hai
      messo, adattandolo se serve. E' per chi la panchina la ordina con cura.
    """

    EASY = "Easy"
    BASIC = "Basic"
    MASTER = "Master"

    @property
    def etichetta(self) -> str:
        return self.value

    @property
    def spiegazione(self) -> str:
        return {
            "EASY": (
                "Entra solo chi puo' occupare quel posto per ruolo. Nessuno "
                "gioca fuori posizione, nemmeno pagando il malus: se non c'e' "
                "il ricambio giusto, il posto vale zero."
            ),
            "BASIC": (
                "Prima si cerca chi occupa il posto senza adattamenti, anche "
                "se sta piu' in fondo in panchina. Solo se non c'e' nessuno "
                "entra il primo disponibile, adattato e con il malus."
            ),
            "MASTER": (
                "Comanda l'ordine della panchina: entra il primo che hai "
                "messo, adattato col malus se il ruolo non torna. Premia chi "
                "la panchina la ordina pensandoci."
            ),
        }[self.name]


# Moduli ammessi dalla piattaforma. In Classic contano i reparti; in Mantra
# contano i ruoli, quindi le combinazioni sono molte di piu'.
MODULI_CLASSIC = (
    "3-4-3",
    "3-5-2",
    "4-3-3",
    "4-4-2",
    "4-5-1",
    "5-3-2",
    "5-4-1",
)

# Gli undici del Mantra, confermati dalla lega a ottobre 2026. Non e' un
# elenco a piacere: nel Mantra i moduli sono quelli e basta, e **la difesa a
# cinque non esiste** — chi la cercava qui dentro la trovava, e il sito
# avrebbe accettato una formazione che la piattaforma rifiuta.
MODULI_MANTRA = (
    "3-4-3",
    "3-4-1-2",
    "3-4-2-1",
    "3-5-2",
    "3-5-1-1",
    "4-3-3",
    "4-3-1-2",
    "4-4-2",
    "4-1-4-1",
    "4-2-3-1",
    "4-3-2-1",
)


def moduli_disponibili(modalita: Modalita) -> tuple[str, ...]:
    return MODULI_MANTRA if modalita is Modalita.MANTRA else MODULI_CLASSIC


@dataclass(frozen=True)
class Bonus:
    """Bonus e malus applicati al voto di ogni giocatore."""

    gol_segnato: float = 3.0
    gol_subito: float = -1.0
    gol_su_rigore: float = 3.0
    rigore_sbagliato: float = -3.0
    rigore_parato: float = 3.0
    autogol: float = -2.0
    assist: float = 1.0
    ammonizione: float = -0.5
    espulsione: float = -1.0
    portiere_imbattuto: float = 1.0


@dataclass(frozen=True)
class FasciaModificatore:
    """Da quale media scatta un bonus di reparto. `a` escluso, `None` = infinito."""

    da: float
    bonus: float

    def contiene(self, media: float, successiva: float | None) -> bool:
        if media < self.da:
            return False
        return successiva is None or media < successiva


# Tabelle di default. Quella della difesa e' la tabella **vera** della lega,
# confermata a ottobre 2026 e verificata sui tabellini di giornata: mezzo
# punto ogni quarto di media, da 6 in su. Le altre due vanno ancora
# confrontate con la piattaforma (vedi PUNTI_APERTI.md). Sono parametri
# proprio perche' cambiarle non deve richiedere di toccare il codice.
FASCE_DIFESA = (
    FasciaModificatore(6.0, 0.5),
    FasciaModificatore(6.25, 1.0),
    FasciaModificatore(6.5, 1.5),
    FasciaModificatore(6.75, 2.0),
    FasciaModificatore(7.0, 2.5),
)

FASCE_CENTROCAMPO = (
    FasciaModificatore(6.5, 1.0),
    FasciaModificatore(7.0, 2.0),
    FasciaModificatore(7.5, 3.0),
)

FASCE_ATTACCO = (
    FasciaModificatore(7.0, 1.0),
    FasciaModificatore(7.5, 2.0),
    FasciaModificatore(8.0, 3.0),
)


def bonus_modificatore(media: float, fasce: tuple[FasciaModificatore, ...]) -> float:
    """Bonus di reparto per una data media voto. Sotto la prima soglia: zero."""
    ordinate = sorted(fasce, key=lambda f: f.da)
    for indice, fascia in enumerate(ordinate):
        successiva = ordinate[indice + 1].da if indice + 1 < len(ordinate) else None
        if fascia.contiene(media, successiva):
            return fascia.bonus
    return 0.0


@dataclass(frozen=True)
class OpzioniLega:
    """Le scelte fatte creando la lega. Tutto qui dentro e' modificabile.

    Corrispondono alle caselle che Leghe Fantacalcio propone in creazione:
    modalita', formato, rosa, asta, formazione, punteggio, modificatori.
    """

    # Impostazioni generali
    modalita: Modalita = Modalita.MANTRA
    partecipanti: int = 10
    formato: FormatoCampionato = FormatoCampionato.ANDATA_RITORNO
    giornate_totali: int = 27

    # Rosa e mercato
    tipo_asta: TipoAsta = TipoAsta.DRAFT
    # Durata massima di un contratto, in anni: e' la leva manageriale della
    # lega, molto piu' dei crediti d'asta che qui non si usano.
    anni_contratto_massimi: int = 5
    # Tetto salariale annuo, in euro. Si sceglie in milioni e si conserva
    # intero: i decimali su cifre a nove zeri sono un modo per perdere euro.
    budget_cap: float = 100_000_000.0
    # `None` = nessun limite per quel ruolo. Il fantacalcio manageriale spesso
    # non li impone: conta il monte anni, non quanti difensori hai.
    rosa_portieri: int | None = 3
    rosa_difensori: int | None = 8
    rosa_centrocampisti: int | None = 8
    rosa_attaccanti: int | None = 6

    # Vincoli di composizione della rosa
    minimo_italiani: int = 0
    minimo_u21_italiani: int = 0
    # Quanti scambi puo' fare una squadra in una stagione. 0 = illimitati.
    scambi_per_stagione: int = 0

    # Dopo una draft room — di inizio stagione o di riparazione — gli anni di
    # contratto si correggono fino all'inizio della giornata successiva: il
    # draft si fa di corsa, e un contratto scritto male va potuto correggere
    # prima che conti. **E' in tensione con l'articolo 8**, che dice che la
    # durata non si tocca «ne' con altra operazione»: finche' la lega non
    # vota, si accende da qui. Vedi PUNTI_APERTI.md e `contratti.py`.
    modifica_anni_dopo_draft: bool = True

    # Draft: l'ordine di chiamata (id delle squadre, dal primo a chiamare) e
    # l'andamento dei round. Vivono qui, e non in una tabella loro, per non
    # chiedere una migrazione del database a chi il sito ce l'ha gia' su.
    ordine_draft: tuple[int, ...] = ()
    draft_serpente: bool = True

    # Formazione
    moduli_ammessi: tuple[str, ...] = MODULI_MANTRA
    panchinari: int = 12
    sostituzioni_automatiche: bool = True
    # Mantra: la gerarchia con cui entra chi sta in panchina. Basic e' il
    # default della piattaforma.
    modalita_sostituzioni: ModalitaSostituzioni = ModalitaSostituzioni.BASIC
    sostituzioni_massime: int = 3
    capitano: bool = True
    vice_capitano: bool = False

    # Punteggio
    bonus: Bonus = field(default_factory=Bonus)
    voto_minimo_senza_voto: float = 6.0
    punti_vittoria: int = 3
    punti_pareggio: int = 1

    # Fasce di gol: il primo gol scatta alla soglia, poi uno ogni passo.
    soglia_primo_gol: float = 66.0
    passo_gol: float = 6.0

    # Competizioni. Il campionato c'e' sempre; le altre si accendono qui.
    coppa_italia: bool = False
    f1_rush: bool = False
    regole_coppa: RegoleCoppa = field(default_factory=RegoleCoppa)
    regole_f1_rush: RegoleF1Rush = field(default_factory=RegoleF1Rush)

    # Modificatori di reparto
    modificatore_difesa: bool = True
    modificatore_centrocampo: bool = False
    modificatore_attacco: bool = False
    fasce_difesa: tuple[FasciaModificatore, ...] = FASCE_DIFESA
    fasce_centrocampo: tuple[FasciaModificatore, ...] = FASCE_CENTROCAMPO
    fasce_attacco: tuple[FasciaModificatore, ...] = FASCE_ATTACCO

    def __post_init__(self) -> None:
        if self.partecipanti < 2:
            raise LegaNonValida("Una lega ha almeno due partecipanti")
        if self.partecipanti > 20:
            raise LegaNonValida("Il massimo previsto e' 20 partecipanti")
        if not self.moduli_ammessi:
            raise LegaNonValida("Serve almeno un modulo ammesso")
        ammessi = set(moduli_disponibili(self.modalita))
        fuori = [m for m in self.moduli_ammessi if m not in ammessi]
        if fuori:
            raise LegaNonValida(
                f"Moduli non previsti in modalita' {self.modalita.etichetta}: "
                f"{', '.join(fuori)}"
            )
        if self.passo_gol <= 0:
            raise LegaNonValida(
                "Il passo fra una fascia di gol e l'altra dev'essere positivo"
            )
        if not 1 <= self.anni_contratto_massimi <= 10:
            raise LegaNonValida("Gli anni di contratto massimi vanno da 1 a 10")
        for etichetta, valore in (
            ("minimo di giocatori italiani", self.minimo_italiani),
            ("minimo di Under 21 italiani", self.minimo_u21_italiani),
            ("numero di scambi per stagione", self.scambi_per_stagione),
            ("numero massimo di sostituzioni", self.sostituzioni_massime),
        ):
            if valore < 0:
                raise LegaNonValida(f"Il {etichetta} non puo' essere negativo")
        if self.minimo_u21_italiani > self.minimo_italiani > 0:
            raise LegaNonValida(
                f"Gli Under 21 italiani richiesti ({self.minimo_u21_italiani}) "
                f"sono piu' del minimo di italiani ({self.minimo_italiani}): "
                f"un Under 21 italiano e' gia' un italiano"
            )
        if self.budget_cap < 0:
            raise LegaNonValida("Il budget cap non puo' essere negativo")
        if self.coppa_italia and self.regole_coppa.squadre_ammesse > self.partecipanti:
            raise LegaNonValida(
                f"La coppa ammette {self.regole_coppa.squadre_ammesse} squadre "
                f"ma la lega ne ha {self.partecipanti}"
            )
        totale = self.rosa_totale
        if totale is not None and self.minimo_italiani > totale:
            raise LegaNonValida(
                f"Servono {self.minimo_italiani} italiani ma la rosa e' di "
                f"{totale} giocatori"
            )

    @property
    def limiti_per_ruolo(self) -> bool:
        """Vero se almeno un ruolo ha un tetto."""
        return any(
            limite is not None
            for limite in (
                self.rosa_portieri,
                self.rosa_difensori,
                self.rosa_centrocampisti,
                self.rosa_attaccanti,
            )
        )

    @property
    def rosa_totale(self) -> int | None:
        """Somma dei limiti di ruolo. `None` se anche uno solo non ha limite.

        Restituire un numero sarebbe peggio che restituire niente: sommare
        ignorando i ruoli liberi darebbe un totale che non vincola nulla.
        """
        limiti = (
            self.rosa_portieri,
            self.rosa_difensori,
            self.rosa_centrocampisti,
            self.rosa_attaccanti,
        )
        if any(limite is None for limite in limiti):
            return None
        return sum(limiti)

    @property
    def budget_cap_milioni(self) -> float:
        return self.budget_cap / 1_000_000

    @property
    def competizioni(self) -> tuple[TipoCompetizione, ...]:
        """Quali competizioni si giocano. Il campionato c'e' sempre."""
        attive = [TipoCompetizione.CAMPIONATO]
        if self.coppa_italia:
            attive.append(TipoCompetizione.COPPA_ITALIA)
        if self.f1_rush:
            attive.append(TipoCompetizione.F1_RUSH)
        return tuple(attive)

    @property
    def scambi_illimitati(self) -> bool:
        return self.scambi_per_stagione <= 0

    def scambi_residui(self, gia_fatti: int) -> int | None:
        """Quanti scambi restano a una squadra. `None` se sono illimitati."""
        if self.scambi_illimitati:
            return None
        return max(0, self.scambi_per_stagione - max(0, gia_fatti))

    def gol_da_punti(self, punti: float) -> int:
        """Quanti gol valgono questi fantapunti, secondo le fasce della lega."""
        if punti < self.soglia_primo_gol:
            return 0
        return 1 + int((punti - self.soglia_primo_gol) // self.passo_gol)

    # --- serializzazione ---------------------------------------------------

    def a_json(self) -> str:
        return json.dumps(_serializza(self), ensure_ascii=False, sort_keys=True)

    @classmethod
    def da_json(cls, testo: str | None) -> OpzioniLega:
        """Ricostruisce le opzioni, ignorando le chiavi che non conosce.

        Ignorare l'ignoto e' voluto: una lega creata con una versione piu'
        recente dell'app non deve rendere illeggibile la riga.
        """
        if not testo:
            return cls()
        try:
            grezzo = json.loads(testo)
        except (TypeError, ValueError):
            return cls()
        if not isinstance(grezzo, dict):
            return cls()
        return cls(**_deserializza(grezzo))


def _serializza(opzioni: OpzioniLega) -> dict:
    dati = asdict(opzioni)
    dati["modalita"] = opzioni.modalita.name
    dati["formato"] = opzioni.formato.name
    dati["tipo_asta"] = opzioni.tipo_asta.name
    dati["modalita_sostituzioni"] = opzioni.modalita_sostituzioni.name
    dati["moduli_ammessi"] = list(opzioni.moduli_ammessi)
    dati["ordine_draft"] = list(opzioni.ordine_draft)
    dati["regole_coppa"] = {
        **asdict(opzioni.regole_coppa),
        "formato": opzioni.regole_coppa.formato.name,
    }
    dati["regole_f1_rush"] = {
        **asdict(opzioni.regole_f1_rush),
        "criterio": opzioni.regole_f1_rush.criterio.name,
        "punti_per_posizione": list(opzioni.regole_f1_rush.punti_per_posizione),
    }
    for campo in ("fasce_difesa", "fasce_centrocampo", "fasce_attacco"):
        dati[campo] = [asdict(f) for f in getattr(opzioni, campo)]
    return dati


def _ricostruisci(grezzo, classe, enumerazioni: dict):
    """Ricostruisce una dataclass annidata, saltando le chiavi che non conosce.

    Restituisce None se il pezzo e' illeggibile: chi chiama usa il default,
    invece di far fallire tutta la lega per un campo scritto male.
    """
    if not isinstance(grezzo, dict):
        return None
    noti = set(classe.__dataclass_fields__)
    valori = {k: v for k, v in grezzo.items() if k in noti}
    for chiave, tipo in enumerazioni.items():
        if chiave in valori:
            try:
                valori[chiave] = tipo[str(valori[chiave])]
            except KeyError:
                valori.pop(chiave)
    try:
        return classe(**valori)
    except (TypeError, ValueError):
        return None


def _deserializza(grezzo: dict) -> dict:
    campi = set(OpzioniLega.__dataclass_fields__)
    valori = {k: v for k, v in grezzo.items() if k in campi}

    # Leghe salvate prima del V3 hanno `supercoppa`, che il V3 ha sostituito
    # con la F1 Rush Finale. Chi l'aveva accesa trova accesa la competizione
    # che l'ha rimpiazzata: perderla in silenzio farebbe sparire una voce di
    # menu senza che nessuno abbia deciso niente.
    if "f1_rush" not in grezzo and "supercoppa" in grezzo:
        valori["f1_rush"] = bool(grezzo["supercoppa"])

    for chiave, tipo in (
        ("modalita", Modalita),
        ("formato", FormatoCampionato),
        ("tipo_asta", TipoAsta),
        ("modalita_sostituzioni", ModalitaSostituzioni),
    ):
        if chiave in valori:
            try:
                valori[chiave] = tipo[str(valori[chiave])]
            except KeyError:
                valori.pop(chiave)

    if "moduli_ammessi" in valori:
        valori["moduli_ammessi"] = tuple(valori["moduli_ammessi"])

    if "ordine_draft" in valori:
        try:
            valori["ordine_draft"] = tuple(int(x) for x in valori["ordine_draft"])
        except (TypeError, ValueError):
            valori.pop("ordine_draft")

    if "bonus" in valori:
        grezzo_bonus = valori["bonus"]
        if isinstance(grezzo_bonus, dict):
            noti = set(Bonus.__dataclass_fields__)
            valori["bonus"] = Bonus(
                **{k: v for k, v in grezzo_bonus.items() if k in noti}
            )
        else:
            valori.pop("bonus")

    for chiave, classe, enumerazioni in (
        ("regole_coppa", RegoleCoppa, {"formato": FormatoCoppa}),
        ("regole_f1_rush", RegoleF1Rush, {"criterio": CriterioF1Rush}),
    ):
        if chiave in valori:
            ricostruito = _ricostruisci(valori[chiave], classe, enumerazioni)
            if ricostruito is None:
                valori.pop(chiave)
            else:
                valori[chiave] = ricostruito

    for campo in ("fasce_difesa", "fasce_centrocampo", "fasce_attacco"):
        if campo in valori:
            try:
                valori[campo] = tuple(
                    FasciaModificatore(float(f["da"]), float(f["bonus"]))
                    for f in valori[campo]
                )
            except (TypeError, KeyError, ValueError):
                valori.pop(campo)

    return valori


# --- La lega ----------------------------------------------------------------


@dataclass(frozen=True)
class Lega:
    """Una lega e i suoi partecipanti. `admin_id` e' l'utente che l'ha creata."""

    id: int
    nome: str
    codice_invito: str
    admin_id: int
    stagione: str = "2026/27"
    opzioni: OpzioniLega = field(default_factory=OpzioniLega)
    creata_il: str = ""

    def __post_init__(self) -> None:
        nome = (self.nome or "").strip()
        if len(nome) < 3:
            raise LegaNonValida("Il nome della lega deve avere almeno 3 caratteri")
        object.__setattr__(self, "nome", nome)
        object.__setattr__(self, "codice_invito", normalizza_codice(self.codice_invito))

    def con_opzioni(self, opzioni: OpzioniLega) -> Lega:
        return replace(self, opzioni=opzioni)


def crea_lega(
    id_: int,
    nome: str,
    admin_id: int,
    opzioni: OpzioniLega | None = None,
    stagione: str = "2026/27",
    codice: str | None = None,
) -> Lega:
    """Costruisce una lega nuova, generando il codice d'invito se non e' dato."""
    return Lega(
        id=id_,
        nome=nome,
        codice_invito=codice or genera_codice_invito(),
        admin_id=admin_id,
        stagione=stagione,
        opzioni=opzioni or OpzioniLega(),
        creata_il=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# --- cambiare le regole a lega gia' avviata ---------------------------------
#
# Le regole si scelgono creando la lega, ma una lega vive: un lodo cambia il
# Salary Cap, la coppa si aggiunge a stagione iniziata, i moduli si
# restringono. Rifare la lega da capo vorrebbe dire perdere rose, calendario
# e albo, quindi si modificano dove sono.


class RegoleNonModificabili(PermissionError):
    """Le regole le cambia chi amministra la lega, e nessun altro."""


def puo_modificare_regole(chi, lega: Lega | None) -> bool:
    """Solo l'amministratore **di quella** lega.

    Si guarda `admin_id` e non il ruolo: il presidente di un'altra lega e' un
    fantallenatore qualunque qui dentro, e il ruolo da solo non lo direbbe.
    L'utente si riceve per struttura e non per tipo perche' `autenticazione`
    importa questo modulo, e il contrario girerebbe in tondo.
    """
    if chi is None or lega is None:
        return False
    if not getattr(chi, "attivo", True):
        return False
    identificativo = getattr(chi, "id", None)
    return identificativo is not None and identificativo == lega.admin_id


def aggiorna_opzioni(
    lega: Lega,
    opzioni: OpzioniLega,
    chi,
    squadre_iscritte: int = 0,
    stagione: str | None = None,
) -> Lega:
    """Le regole nuove, con i controlli che dipendono da come sta la lega.

    `OpzioniLega` sa gia' dire se una regola e' assurda in se' (un passo di gol
    negativo, moduli che non esistono in quella modalita'). Qui si aggiunge
    l'unica cosa che quella non puo' sapere: com'e' messa **questa** lega
    adesso. Ridurre i partecipanti sotto il numero di squadre gia' iscritte
    lascerebbe fuori qualcuno che sta giocando, e non e' un errore che si
    scopre a giornata in corso.
    """
    if not puo_modificare_regole(chi, lega):
        raise RegoleNonModificabili(
            "Solo chi ha creato la lega puo' cambiarne le regole."
        )
    if squadre_iscritte > opzioni.partecipanti:
        raise LegaNonValida(
            f"La lega ha gia' {squadre_iscritte} squadre iscritte: non puoi "
            f"portare i partecipanti a {opzioni.partecipanti}."
        )
    aggiornata = replace(lega, opzioni=opzioni)
    if stagione is not None and stagione.strip():
        aggiornata = replace(aggiornata, stagione=stagione.strip())
    return aggiornata


# Come si chiama, per un essere umano, ogni casella delle opzioni. Quelle che
# non stanno qui si leggono lo stesso: il nome del campo con gli underscore
# tolti e' quasi sempre comprensibile.
ETICHETTE_OPZIONI: dict[str, str] = {
    "modalita": "Modalita'",
    "partecipanti": "Partecipanti",
    "formato": "Formato del campionato",
    "giornate_totali": "Giornate totali",
    "tipo_asta": "Come si assegnano i giocatori",
    "anni_contratto_massimi": "Anni di contratto massimi",
    "budget_cap": "Budget cap",
    "rosa_portieri": "Portieri in rosa",
    "rosa_difensori": "Difensori in rosa",
    "rosa_centrocampisti": "Centrocampisti in rosa",
    "rosa_attaccanti": "Attaccanti in rosa",
    "minimo_italiani": "Minimo italiani",
    "minimo_u21_italiani": "Minimo Under 21 italiani",
    "scambi_per_stagione": "Scambi a stagione",
    "moduli_ammessi": "Moduli ammessi",
    "panchinari": "Panchinari",
    "sostituzioni_automatiche": "Sostituzioni automatiche",
    "modalita_sostituzioni": "Modalita' delle sostituzioni",
    "sostituzioni_massime": "Sostituzioni per giornata",
    "capitano": "Capitano",
    "punti_vittoria": "Punti per vittoria",
    "punti_pareggio": "Punti per pareggio",
    "soglia_primo_gol": "Punti per il primo gol",
    "passo_gol": "Punti per ogni gol successivo",
    "voto_minimo_senza_voto": "Voto d'ufficio a chi non gioca",
    "coppa_italia": "Coppa Italia",
    "f1_rush": "F1 Rush Finale",
    "modificatore_difesa": "Modificatore difesa",
    "modificatore_centrocampo": "Modificatore centrocampo",
    "modificatore_attacco": "Modificatore attacco",
    "bonus": "Bonus e malus",
    "regole_coppa": "Regole della Coppa Italia",
    "regole_f1_rush": "Regole della F1 Rush Finale",
    # I campi dentro i tre oggetti annidati. Si cercano col nome corto
    # («assist»), perche' e' quello che resta dopo il punto.
    "gol_segnato": "Gol segnato",
    "gol_su_rigore": "Gol su rigore",
    "gol_subito": "Gol subito",
    "assist": "Assist",
    "rigore_parato": "Rigore parato",
    "rigore_sbagliato": "Rigore sbagliato",
    "autogol": "Autogol",
    "ammonizione": "Ammonizione",
    "espulsione": "Espulsione",
    "portiere_imbattuto": "Portiere imbattuto",
    "regole_coppa.formato": "Formato della coppa",
    "squadre_ammesse": "Squadre ammesse",
    "gironi": "Gironi",
    "qualificate_per_girone": "Qualificate per girone",
    "dopo_il_campionato": "Si gioca a fine campionato",
    "prima_giornata": "Primo turno alla giornata",
    "ogni_quante_giornate": "Un turno ogni quante giornate",
    "teste_di_serie": "Teste di serie",
    "spareggio_ai_fantapunti": "Spareggio ai fantapunti",
    "finale_in_campo_neutro": "Finale in campo neutro",
    "criterio": "Criterio della F1 Rush",
    "giornate_serie_a": "Giornate di Serie A",
    "punti_per_posizione": "Punti di tappa",
}


def _leggibile(valore) -> str:
    """Un valore come lo scriverebbe una persona, non come lo stampa Python."""
    if isinstance(valore, bool):
        return "si" if valore else "no"
    if valore is None:
        return "nessun limite"
    if isinstance(valore, Enum):
        return getattr(valore, "etichetta", valore.name)
    if isinstance(valore, tuple | list):
        return ", ".join(_leggibile(v) for v in valore) if valore else "nessuno"
    if isinstance(valore, float) and valore.is_integer():
        return str(int(valore))
    return str(valore)


def differenze(prima: OpzioniLega, dopo: OpzioniLega) -> list[str]:
    """Cosa cambia fra due versioni delle regole, in italiano.

    Serve a farlo leggere prima di salvare: una regola cambiata per sbaglio la
    scoprirebbero dieci persone a giornata in corso, ed e' il tipo di errore
    che costa piu' di quanto costi rileggere una riga.
    """
    cambiate: list[str] = []
    for campo in OpzioniLega.__dataclass_fields__:
        vecchio = getattr(prima, campo)
        nuovo = getattr(dopo, campo)
        if vecchio == nuovo:
            continue
        # Bonus, coppa e F1 Rush sono oggetti: stamparli interi vorrebbe dire
        # mettere davanti a chi salva due righe di `Bonus(gol_segnato=3.0,
        # ...)` da confrontare a occhio. Si scende di un livello e si dice
        # solo il campo che e' cambiato davvero.
        if is_dataclass(vecchio) and type(vecchio) is type(nuovo):
            for interno in type(vecchio).__dataclass_fields__:
                dentro_prima = getattr(vecchio, interno)
                dentro_dopo = getattr(nuovo, interno)
                if dentro_prima == dentro_dopo:
                    continue
                cambiate.append(
                    f"{_etichetta_di(f'{campo}.{interno}')}: "
                    f"{_leggibile(dentro_prima)} → {_leggibile(dentro_dopo)}"
                )
            continue
        etichetta = ETICHETTE_OPZIONI.get(campo, campo.replace("_", " ").capitalize())
        if campo == "budget_cap":
            vecchio, nuovo = f"{vecchio / 1e6:g}M", f"{nuovo / 1e6:g}M"
        cambiate.append(f"{etichetta}: {_leggibile(vecchio)} → {_leggibile(nuovo)}")
    return cambiate


def avvisi_sulle_regole(
    opzioni: OpzioniLega, nuove: OpzioniLega, squadre_iscritte: int = 0
) -> list[str]:
    """Le conseguenze che il salvataggio non rifiuta, ma che conviene sapere.

    Non sono errori: sono cambiamenti legittimi che pero' toccano roba gia'
    salvata — formazioni schierate, giornate calcolate — e vale la pena dirli
    prima invece di lasciarli scoprire a giornata in corso.
    """
    avvisi: list[str] = []

    if squadre_iscritte > nuove.partecipanti:
        avvisi.append(
            f"La lega ha {squadre_iscritte} squadre iscritte e staresti "
            f"mettendo il tetto a {nuove.partecipanti}: il salvataggio lo "
            f"rifiutera'."
        )

    tolti = [m for m in opzioni.moduli_ammessi if m not in nuove.moduli_ammessi]
    if tolti:
        avvisi.append(
            f"Moduli tolti: {', '.join(tolti)}. Chi li aveva gia' usati "
            f"trovera' la formazione da rifare."
        )

    if nuove.panchinari < opzioni.panchinari:
        avvisi.append(
            f"La panchina passa da {opzioni.panchinari} a {nuove.panchinari}: "
            f"le formazioni salvate con piu' panchinari vanno risistemate."
        )

    if (
        nuove.soglia_primo_gol != opzioni.soglia_primo_gol
        or nuove.passo_gol != opzioni.passo_gol
    ):
        avvisi.append(
            "Cambiano le fasce di gol: le giornate gia' calcolate restano come "
            "sono, le prossime useranno le fasce nuove. Per riallineare anche "
            "il passato bisogna ricalcolare quelle giornate."
        )

    if nuove.modalita is not opzioni.modalita:
        avvisi.append(
            f"Stai passando a {nuove.modalita.etichetta}: cambiano i ruoli con "
            f"cui si schiera, e i moduli con loro."
        )

    return avvisi


def trova_per_codice(leghe: dict[int, Lega], codice: str) -> Lega | None:
    """Cerca la lega da un codice scritto a mano. None se non esiste."""
    try:
        cercato = normalizza_codice(codice)
    except CodiceNonValido:
        return None
    for lega in leghe.values():
        if lega.codice_invito == cercato:
            return lega
    return None


# --- Inviti per email -------------------------------------------------------


class StatoInvito(Enum):
    IN_ATTESA = "in_attesa"
    ACCETTATO = "accettato"
    ANNULLATO = "annullato"

    @property
    def etichetta(self) -> str:
        return {
            "in_attesa": "In attesa",
            "accettato": "Accettato",
            "annullato": "Annullato",
        }[self.value]


@dataclass(frozen=True)
class Invito:
    """Un posto riservato a un indirizzo email.

    L'app non manda mail: non ha un server di posta e aggiungerne uno per dieci
    persone non si giustifica. L'invito registra *chi* e' atteso; il codice si
    gira a mano, e chi arriva con quell'email trova il posto gia' pronto.
    """

    id: int
    lega_id: int
    email: str
    codice: str
    stato: StatoInvito = StatoInvito.IN_ATTESA
    creato_da: int | None = None
    creato_il: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "email", normalizza_email(self.email))
        object.__setattr__(self, "codice", normalizza_codice(self.codice))

    @property
    def in_attesa(self) -> bool:
        return self.stato is StatoInvito.IN_ATTESA


def crea_invito(id_: int, lega: Lega, email: str, creato_da: int | None = None) -> Invito:
    return Invito(
        id=id_,
        lega_id=lega.id,
        email=email,
        codice=lega.codice_invito,
        creato_da=creato_da,
        creato_il=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def invito_per_email(inviti: list[Invito], lega_id: int, email: str) -> Invito | None:
    try:
        cercata = normalizza_email(email)
    except EmailNonValida:
        return None
    for invito in inviti:
        if invito.lega_id == lega_id and invito.email == cercata and invito.in_attesa:
            return invito
    return None


def parametri_di_punteggio(base: ParametriLega, lega: Lega | None) -> ParametriLega:
    """I parametri con cui si calcola una giornata in questa lega.

    Le fasce dei gol e il modificatore difesa stanno nel regolamento, ma la
    lega puo' averli cambiati per votazione: qui le due cose si incontrano
    **una volta sola**, cosi' chi calcola non deve scegliere ogni volta quale
    delle due guardare — ed e' il genere di scelta che due schermate fanno in
    modi diversi senza che nessuno se ne accorga.
    """
    if lega is None:
        return base
    return replace(
        base,
        soglia_primo_gol=lega.opzioni.soglia_primo_gol,
        passo_gol=lega.opzioni.passo_gol,
        modificatore_difesa=lega.opzioni.modificatore_difesa,
    )


# ---------------------------------------------------------------------------
# Il regolamento applicato, in righe
# ---------------------------------------------------------------------------
#
# La pagina «Regolamento» non e' altro che gruppi di «voce -> valore». Stavano
# scritti dentro la vista Streamlit: riscriverli nell'API avrebbe voluto dire
# due elenchi da aggiornare a ogni lodo, e il secondo sarebbe rimasto indietro
# in silenzio — e' esattamente quello che `scheda_regolamento` evita per la
# chat. Qui si costruiscono una volta, e le due interfacce li mostrano.


@dataclass(frozen=True)
class VoceRegolamento:
    voce: str
    valore: str


@dataclass(frozen=True)
class GruppoRegolamento:
    titolo: str
    voci: tuple[VoceRegolamento, ...]
    nota: str = ""


def _milioni(importo: float) -> str:
    return f"{importo / 1_000_000:.0f} milioni"


def prospetto_regolamento(
    parametri: ParametriLega,
    opzioni: OpzioniLega,
    data_u21,
    lega: Lega | None = None,
) -> tuple[GruppoRegolamento, ...]:
    """I valori che il gestionale applica davvero, raggruppati per articolo.

    Prende i parametri gia' risolti invece di andarseli a prendere: la data
    Under 21 la sa chi chiama (la lega la fissa al 31 agosto), e cosi' la
    funzione resta pura e si prova senza database.

    **I parametri si rifondono qui con le opzioni.** Il gruppo «Punteggio»
    dice i valori che il sito applica, e quelli li decide
    `parametri_di_punteggio`: leggendo i parametri grezzi, una lega che ha
    votato il primo gol a 60 avrebbe letto 66 nel gruppo che promette di dire
    cosa si applica, contraddicendo il gruppo «Le scelte di questa lega» due
    tabelle piu' su.
    """
    v = VoceRegolamento
    p = parametri_di_punteggio(parametri, lega) if lega else parametri

    lega = [
        v("Modalita'", opzioni.modalita.etichetta),
        v("Partecipanti", str(opzioni.partecipanti)),
        v("Formato del campionato", opzioni.formato.etichetta),
        v("Giornate", str(opzioni.giornate_totali)),
        v("Assegnazione dei giocatori", opzioni.tipo_asta.etichetta),
        v("Anni di contratto (massimo)", str(opzioni.anni_contratto_massimi)),
        v("Budget cap annuale", f"{opzioni.budget_cap_milioni:.0f} milioni"),
        v(
            "Limiti per ruolo",
            (
                f"{opzioni.rosa_portieri} Por · {opzioni.rosa_difensori} Dif · "
                f"{opzioni.rosa_centrocampisti} Cen · {opzioni.rosa_attaccanti} Att"
                if opzioni.limiti_per_ruolo and opzioni.rosa_totale
                else "nessun limite per ruolo"
            ),
        ),
        v(
            "Minimo giocatori italiani",
            str(opzioni.minimo_italiani) if opzioni.minimo_italiani else "nessun vincolo",
        ),
        v(
            "Minimo Under 21 italiani",
            str(opzioni.minimo_u21_italiani)
            if opzioni.minimo_u21_italiani
            else "nessun vincolo",
        ),
        v(
            "Scambi per stagione",
            "illimitati"
            if opzioni.scambi_illimitati
            else f"{opzioni.scambi_per_stagione} per squadra",
        ),
        v("Under 21: data di riferimento", data_u21.strftime("%d/%m/%Y")),
        v("Primo gol", f"{opzioni.soglia_primo_gol:g} punti"),
        v("Gol successivi", f"uno ogni {opzioni.passo_gol:g} punti"),
        v(
            "Competizioni",
            " · ".join(f"{c.icona} {c.etichetta}" for c in opzioni.competizioni),
        ),
    ]

    gruppi = [
        GruppoRegolamento(
            "Le scelte di questa lega",
            tuple(lega),
            "Decise creando la lega. Valgono insieme al regolamento: dove i "
            "numeri differiscono, comanda quello scelto qui.",
        ),
        GruppoRegolamento(
            "Composizione rosa (art. 2)",
            (
                v("Giocatori minimi", str(p.rosa_minimo)),
                v("Giocatori massimi", str(p.rosa_massimo_base)),
                v("Massimo con espansione Under 21", str(p.rosa_massimo_assoluto)),
                v("Portieri massimi", str(p.portieri_massimo)),
                v("Portieri minimi", str(p.portieri_minimo)),
                v("Slot Under 21 massimi", str(p.slot_u21_massimi)),
                v("Eta' limite Under 21", str(p.eta_limite_u21)),
                v("Monte anni", str(p.monte_anni)),
                v(
                    "Anni per contratto",
                    f"da {p.contratto_anni_minimo} a {p.contratto_anni_massimo}",
                ),
            ),
        ),
        GruppoRegolamento(
            "Regola «1/3»: contratti annuali obbligatori",
            tuple(
                v(f"{s.rosa_da}-{s.rosa_a} giocatori", str(s.minimo_annuali))
                for s in p.soglie_annuali
            ),
        ),
        GruppoRegolamento(
            "Economia (art. 4 e 7)",
            (
                v("Salary Cap", _milioni(p.salary_cap)),
                v("Salary Floor", _milioni(p.salary_floor)),
                v("Salary Floor attivo", "Si'" if p.salary_floor_attivo else "No"),
                v(
                    "Dead Money da svincolo",
                    f"{p.quota_dead_money:.0%} del valore residuo",
                ),
                v("Fonte ingaggi", "Capology"),
            ),
        ),
        GruppoRegolamento(
            "Mercato e scambi (art. 5, 6 e 8)",
            (
                v("Giornate per gironcino", str(p.giornate_per_gironcino)),
                v(
                    "Prolungamenti e riduzioni di durata",
                    "ammessi" if p.prolungamenti_ammessi else "non ammessi (art. 8)",
                ),
                *(
                    (
                        v(
                            "Prolungamenti per squadra a stagione (Lodo Longoni)",
                            str(p.prolungamenti_per_squadra_a_stagione),
                        ),
                        v(
                            "Prolungamenti per giocatore in lega (Lodo Corti)",
                            str(p.prolungamenti_per_giocatore_in_lega),
                        ),
                    )
                    if p.prolungamenti_ammessi
                    else ()
                ),
                v(
                    "Preavviso di ratifica di uno scambio",
                    f"{p.ore_ratifica_scambio} ore",
                ),
            ),
        ),
        GruppoRegolamento(
            "Punteggio (art. 1)",
            (
                v("Modalita'", opzioni.modalita.etichetta),
                v("Fonte voti", "Statistico + Redazione"),
                v("Primo gol a", f"{p.soglia_primo_gol:.0f} punti"),
                v("Poi un gol ogni", f"{p.passo_gol:.0f} punti"),
                v(
                    "Modificatore di difesa",
                    "Attivo" if p.modificatore_difesa else "Disattivo",
                ),
                v(
                    "Malus per chi gioca fuori posizione",
                    f"−{abs(p.malus_adattamento):g}",
                ),
            ),
        ),
    ]
    return tuple(gruppi)


# ---------------------------------------------------------------------------
# Le regole come modulo: una descrizione che il sito disegna da sola
# ---------------------------------------------------------------------------
#
# Il modulo per cambiare le regole non si scrive a mano casella per casella.
# Sarebbe una terza copia dell'elenco delle opzioni — dopo la dataclass e le
# etichette — e la terza copia e' quella che si dimentica: un'opzione aggiunta
# domani resterebbe invisibile, e nessuno se ne accorgerebbe finche' qualcuno
# non la cerca. Qui si descrive, e chi disegna il modulo segue la descrizione.
#
# E' lo stesso patto del dossier della chat sul regolamento: un parametro
# nuovo arriva da solo, e un test parametrizzato lo pretende.

# I gruppi, nell'ordine in cui si leggono. Un campo che non sta qui dentro non
# si puo' cambiare dal sito: `FUORI_MODULO` dice quali e perche'.
GRUPPI_OPZIONI: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Generali",
        (
            "modalita",
            "partecipanti",
            "formato",
            "giornate_totali",
            "punti_vittoria",
            "punti_pareggio",
        ),
    ),
    (
        "Rosa e mercato",
        (
            "tipo_asta",
            "anni_contratto_massimi",
            "budget_cap",
            "rosa_portieri",
            "rosa_difensori",
            "rosa_centrocampisti",
            "rosa_attaccanti",
            "minimo_italiani",
            "minimo_u21_italiani",
            "scambi_per_stagione",
            "modifica_anni_dopo_draft",
            "draft_serpente",
        ),
    ),
    (
        "Formazione",
        (
            "moduli_ammessi",
            "panchinari",
            "sostituzioni_automatiche",
            "modalita_sostituzioni",
            "sostituzioni_massime",
            "capitano",
            "vice_capitano",
        ),
    ),
    (
        "Punteggio",
        (
            "voto_minimo_senza_voto",
            "soglia_primo_gol",
            "passo_gol",
            "bonus.gol_segnato",
            "bonus.gol_su_rigore",
            "bonus.gol_subito",
            "bonus.assist",
            "bonus.rigore_parato",
            "bonus.rigore_sbagliato",
            "bonus.autogol",
            "bonus.ammonizione",
            "bonus.espulsione",
            "bonus.portiere_imbattuto",
        ),
    ),
    (
        "Modificatori di reparto",
        ("modificatore_difesa", "modificatore_centrocampo", "modificatore_attacco"),
    ),
    (
        "Competizioni",
        (
            "coppa_italia",
            "regole_coppa.formato",
            "regole_coppa.squadre_ammesse",
            "regole_coppa.gironi",
            "regole_coppa.qualificate_per_girone",
            "regole_coppa.dopo_il_campionato",
            "regole_coppa.prima_giornata",
            "regole_coppa.ogni_quante_giornate",
            "regole_coppa.teste_di_serie",
            "regole_coppa.spareggio_ai_fantapunti",
            "regole_coppa.finale_in_campo_neutro",
            "f1_rush",
            "regole_f1_rush.criterio",
            "regole_f1_rush.giornate_serie_a",
            "regole_f1_rush.punti_per_posizione",
        ),
    ),
)

# I campi che dal modulo restano fuori, con il motivo. Il motivo si mostra:
# un'opzione che esiste e non si vede sembra un pezzo rotto del sito.
FUORI_MODULO: dict[str, str] = {
    "ordine_draft": (
        "L'ordine di chiamata lo decide la Draft Room, che lo congela "
        "all'apertura: cambiarlo qui non toccherebbe una sala gia' aperta."
    ),
    "fasce_difesa": (
        "Le fasce dei modificatori sono le tabelle dell'articolo 1: si "
        "accendono e si spengono, non si riscrivono per votazione."
    ),
    "fasce_centrocampo": (
        "Come le fasce di difesa: si accende il modificatore, non la tabella."
    ),
    "fasce_attacco": (
        "Come le fasce di difesa: si accende il modificatore, non la tabella."
    ),
}

# I tre oggetti annidati — bonus, regole della coppa, regole della F1 Rush —
# non stanno ne' qui ne' fra i gruppi col loro nome: ci stanno i loro campi,
# uno per uno, scritti «bonus.assist».


@dataclass(frozen=True)
class SceltaOpzione:
    """Una delle voci ammesse per un campo a scelta."""

    valore: str
    etichetta: str


# Le caselle che si scrivono in un'unita' diversa da quella in cui si
# conservano. Il Salary Cap sta in euro — i decimali su cifre a nove zeri
# sono un modo per perdere euro — ma nessuno lo dice in euro: la lega vota
# «cento milioni», e scrivere 100000000 a mano e' un modo per sbagliare uno
# zero senza accorgersene.
IN_MILIONI = ("budget_cap",)


@dataclass(frozen=True)
class CampoOpzione:
    """Una casella del modulo, con dentro tutto quel che serve a disegnarla."""

    nome: str
    etichetta: str
    # intero | decimale | booleano | scelta | multi | testo
    tipo: str
    valore: object
    scelte: tuple[SceltaOpzione, ...] = ()
    # Vero quando il campo ammette «nessun limite»: i tetti per ruolo lo fanno.
    opzionale: bool = False
    # Come si legge il numero: "" o "milioni". Chi disegna il modulo lo
    # scrive accanto alla casella, e il valore qui dentro e' gia' convertito.
    unita: str = ""


@dataclass(frozen=True)
class GruppoOpzioni:
    titolo: str
    campi: tuple[CampoOpzione, ...]


def _annotazione(nome: str) -> str:
    """Il tipo scritto nella dataclass, come testo."""
    radice, _, resto = nome.partition(".")
    if not resto:
        campo = OpzioniLega.__dataclass_fields__.get(radice)
        return str(campo.type) if campo else ""
    contenitore = type(getattr(OpzioniLega(), radice))
    campo = contenitore.__dataclass_fields__.get(resto)
    return str(campo.type) if campo else ""


def _valore_di(opzioni: OpzioniLega, nome: str):
    radice, _, resto = nome.partition(".")
    valore = getattr(opzioni, radice)
    return getattr(valore, resto) if resto else valore


def _etichetta_di(nome: str) -> str:
    if nome in ETICHETTE_OPZIONI:
        return ETICHETTE_OPZIONI[nome]
    ultimo = nome.rpartition(".")[2]
    return ETICHETTE_OPZIONI.get(ultimo, ultimo.replace("_", " ").capitalize())


def descrivi_opzioni(opzioni: OpzioniLega) -> list[GruppoOpzioni]:
    """Le regole di questa lega, raccontate come un modulo da compilare.

    Il tipo di ogni casella si ricava dal valore che ha adesso — un Enum porta
    con se' le sue voci, un booleano e' un interruttore — e non da una tabella
    scritta a mano che il giorno dopo dice un'altra cosa.
    """
    gruppi: list[GruppoOpzioni] = []
    for titolo, nomi in GRUPPI_OPZIONI:
        campi: list[CampoOpzione] = []
        for nome in nomi:
            valore = _valore_di(opzioni, nome)
            scelte: tuple[SceltaOpzione, ...] = ()
            opzionale = "None" in _annotazione(nome)

            if isinstance(valore, bool):
                tipo = "booleano"
            elif isinstance(valore, Enum):
                tipo = "scelta"
                scelte = tuple(
                    SceltaOpzione(v.name, getattr(v, "etichetta", v.name))
                    for v in type(valore)
                )
                valore = valore.name
            elif nome == "moduli_ammessi":
                # Le scelte dipendono dalla modalita', che e' un'altra casella
                # dello stesso modulo: Mantra e Classic hanno moduli diversi.
                tipo = "multi"
                scelte = tuple(
                    SceltaOpzione(m, m) for m in moduli_disponibili(opzioni.modalita)
                )
                valore = list(valore)
            elif isinstance(valore, tuple | list):
                # Una scala di numeri (i punti di tappa della F1 Rush): si
                # scrive come la si legge, «25, 18, 15, …».
                tipo = "testo"
                valore = ", ".join(str(v) for v in valore)
            elif isinstance(valore, int) and not isinstance(valore, bool):
                tipo = "intero"
            elif isinstance(valore, float):
                tipo = "decimale"
            elif valore is None:
                tipo = "intero"
            else:
                tipo = "testo"

            unita = ""
            if nome in IN_MILIONI:
                unita, valore = "milioni", float(valore) / 1_000_000

            campi.append(
                CampoOpzione(
                    nome=nome,
                    etichetta=_etichetta_di(nome),
                    tipo=tipo,
                    valore=valore,
                    scelte=scelte,
                    opzionale=opzionale,
                    unita=unita,
                )
            )
        gruppi.append(GruppoOpzioni(titolo, tuple(campi)))
    return gruppi


def _converti(nome: str, grezzo, adesso):
    """Il valore che arriva dal modulo, riportato al tipo che aveva."""
    if nome in IN_MILIONI:
        return float(grezzo) * 1_000_000
    if isinstance(adesso, bool):
        return bool(grezzo)
    if isinstance(adesso, Enum):
        try:
            return type(adesso)[str(grezzo)]
        except KeyError as errore:
            raise LegaNonValida(
                f"«{grezzo}» non e' un valore ammesso per {_etichetta_di(nome)}."
            ) from errore
    if nome == "moduli_ammessi":
        return tuple(str(m) for m in grezzo)
    if isinstance(adesso, tuple):
        pezzi = [p.strip() for p in str(grezzo).replace(";", ",").split(",")]
        try:
            return tuple(int(p) for p in pezzi if p)
        except ValueError as errore:
            raise LegaNonValida(
                f"{_etichetta_di(nome)}: servono numeri separati da virgola."
            ) from errore
    if grezzo in (None, "") and "None" in _annotazione(nome):
        return None
    if isinstance(adesso, float):
        return float(grezzo)
    if isinstance(adesso, int) or adesso is None:
        return int(grezzo)
    return str(grezzo)


def con_valori(opzioni: OpzioniLega, valori: dict) -> OpzioniLega:
    """Le opzioni con dentro i valori del modulo, e nient'altro.

    Un nome che il modulo non conosce **ferma tutto**: una casella scritta
    male verrebbe ignorata in silenzio, e chi l'ha compilata crederebbe di
    aver cambiato una regola che invece e' rimasta com'era.

    I controlli veri restano dove sono sempre stati — `__post_init__` di
    `OpzioniLega` e `aggiorna_opzioni` — e le loro eccezioni passano di qui
    senza essere mascherate.
    """
    ammessi = {nome for _, nomi in GRUPPI_OPZIONI for nome in nomi}
    sconosciuti = sorted(set(valori) - ammessi)
    if sconosciuti:
        raise LegaNonValida(f"Opzioni che non esistono: {', '.join(sconosciuti)}.")

    piatti: dict[str, object] = {}
    annidati: dict[str, dict[str, object]] = {}
    for nome, grezzo in valori.items():
        convertito = _converti(nome, grezzo, _valore_di(opzioni, nome))
        radice, _, resto = nome.partition(".")
        if resto:
            annidati.setdefault(radice, {})[resto] = convertito
        else:
            piatti[radice] = convertito

    for radice, campi in annidati.items():
        piatti[radice] = replace(getattr(opzioni, radice), **campi)
    return replace(opzioni, **piatti)
