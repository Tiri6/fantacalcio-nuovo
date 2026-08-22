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
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum

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

MODULI_MANTRA = (
    "3-4-3",
    "3-4-1-2",
    "3-4-2-1",
    "3-5-2",
    "3-5-1-1",
    "4-3-3",
    "4-4-2",
    "4-3-1-2",
    "4-1-4-1",
    "4-2-3-1",
    "4-4-1-1",
    "4-3-2-1",
    "5-3-2",
    "5-4-1",
    "5-2-2-1",
    "5-3-1-1",
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


# Tabelle di default. NOTA: le soglie esatte della piattaforma vanno
# confermate dalla lega — vedi PUNTI_APERTI.md. Sono parametri proprio perche'
# cambiarle non deve richiedere di toccare il codice.
FASCE_DIFESA = (
    FasciaModificatore(6.0, 1.0),
    FasciaModificatore(6.25, 2.0),
    FasciaModificatore(6.5, 3.0),
    FasciaModificatore(6.75, 4.0),
    FasciaModificatore(7.0, 5.0),
    FasciaModificatore(7.25, 6.0),
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

    # Rosa e asta
    tipo_asta: TipoAsta = TipoAsta.DRAFT
    crediti_iniziali: int = 500
    rosa_portieri: int = 3
    rosa_difensori: int = 8
    rosa_centrocampisti: int = 8
    rosa_attaccanti: int = 6

    # Formazione
    moduli_ammessi: tuple[str, ...] = MODULI_MANTRA
    panchinari: int = 12
    sostituzioni_automatiche: bool = True
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

    @property
    def rosa_totale(self) -> int:
        return (
            self.rosa_portieri
            + self.rosa_difensori
            + self.rosa_centrocampisti
            + self.rosa_attaccanti
        )

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
    dati["moduli_ammessi"] = list(opzioni.moduli_ammessi)
    for campo in ("fasce_difesa", "fasce_centrocampo", "fasce_attacco"):
        dati[campo] = [asdict(f) for f in getattr(opzioni, campo)]
    return dati


def _deserializza(grezzo: dict) -> dict:
    campi = set(OpzioniLega.__dataclass_fields__)
    valori = {k: v for k, v in grezzo.items() if k in campi}

    for chiave, tipo in (
        ("modalita", Modalita),
        ("formato", FormatoCampionato),
        ("tipo_asta", TipoAsta),
    ):
        if chiave in valori:
            try:
                valori[chiave] = tipo[str(valori[chiave])]
            except KeyError:
                valori.pop(chiave)

    if "moduli_ammessi" in valori:
        valori["moduli_ammessi"] = tuple(valori["moduli_ammessi"])

    if "bonus" in valori:
        grezzo_bonus = valori["bonus"]
        if isinstance(grezzo_bonus, dict):
            noti = set(Bonus.__dataclass_fields__)
            valori["bonus"] = Bonus(
                **{k: v for k, v in grezzo_bonus.items() if k in noti}
            )
        else:
            valori.pop("bonus")

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
