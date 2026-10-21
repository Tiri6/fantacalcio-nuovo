"""Formazioni: chi schieri, fino a quando puoi cambiarle, e quanto fanno.

E' il giro base di ogni fantacalcio, e qui si divide in quattro pezzi che non
si conoscono fra loro:

- **i moduli**: da «3-4-1-2» ai posti da riempire, reparto per reparto;
- **la validazione**: undici titolari, tutti in rosa, ognuno in un reparto che
  puo' occupare;
- **il blocco**: dal minuto prima del calcio d'inizio non si tocca piu';
- **il punteggio**: voti piu' bonus, le sostituzioni di chi non ha giocato, il
  modificatore di difesa, e infine i gol dalle fasce della lega.

Nessuno di questi importa Streamlit: si provano tutti senza aprire il sito.

Una precisazione onesta sui moduli Mantra. Leghe Fantacalcio applica una
tabella di slot molto piu' fine della nostra: ogni modulo prescrive i ruoli
esatti, non solo quanti difensori e quanti centrocampisti. Qui si controlla
**per reparto**, con i ruoli di confine (E, W, T) validi in due reparti. E'
una approssimazione dichiarata, non una svista: sta in PUNTI_APERTI.md, e
serve a non rifiutare una formazione che la piattaforma vera accetterebbe.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .leghe import (
    Bonus,
    FasciaModificatore,
    ModalitaSostituzioni,
    bonus_modificatore,
)
from .mantra import Esito, caselle_di, esito_in_casella
from .regole import ParametriLega, fasce_gol


class FormazioneNonValida(ValueError):
    """La formazione non si puo' schierare, e il messaggio dice perche'."""


class Reparto(Enum):
    """I quattro reparti, con i ruoli Mantra che li possono occupare."""

    PORTA = ("Porta", ("Por",))
    DIFESA = ("Difesa", ("Dc", "Dd", "Ds", "B", "E"))
    CENTROCAMPO = ("Centrocampo", ("E", "M", "C", "W", "T"))
    ATTACCO = ("Attacco", ("W", "T", "A", "Pc"))

    def __init__(self, etichetta: str, ruoli: tuple[str, ...]):
        self.etichetta = etichetta
        self.ruoli = ruoli

    def accetta(self, ruoli_giocatore: tuple[str, ...]) -> bool:
        return any(ruolo in self.ruoli for ruolo in ruoli_giocatore)


# La lettera con cui un reparto si scrive sui badge: P, D, C, A.
SIGLE_REPARTO = {
    Reparto.PORTA: "P",
    Reparto.DIFESA: "D",
    Reparto.CENTROCAMPO: "C",
    Reparto.ATTACCO: "A",
}


def reparto_principale(ruoli: tuple[str, ...]) -> Reparto | None:
    """Il reparto «di casa» di un giocatore, per chi deve raggrupparli o filtrarli.

    Si guarda il **primo ruolo** della scheda e il primo reparto, nell'ordine
    porta-difesa-centrocampo-attacco, che lo ammette: un «E» e' un difensore
    (come per il modificatore di difesa), una «W» o un «T» un centrocampista.
    Serve solo a etichettare: dove puo' giocare davvero lo dicono le caselle.
    """
    for ruolo in ruoli:
        for reparto in Reparto:
            if ruolo in reparto.ruoli:
                return reparto
    return None


# I ruoli di confine valgono in due reparti: l'esterno «E» fa il terzino o
# l'ala di centrocampo, l'ala «W» e il trequartista «T» giocano avanzati o in
# mezzo. E' il motivo per cui i reparti sopra si sovrappongono.
RUOLI_DI_CONFINE = ("E", "W", "T")

# Chi entra nella media del modificatore di difesa. L'esterno c'e' dentro
# anche quando gioca in una casella di centrocampo: in un 3-4-x i due «E»
# sono i quinti, e per la piattaforma restano difensori.
RUOLI_DIFENSIVI = ("Dd", "Ds", "Dc", "B", "E")

TITOLARI = 11


@dataclass(frozen=True)
class Casella:
    """Un posto del modulo: quali ruoli ci stanno di diritto, e in che riga.

    E' l'unita' vera del Mantra. «Tre difensori» non vuol dire niente: il
    3-4-3 chiede *Dc, Dc, Dc/B*, e un terzino li' dentro si adatta e paga.
    """

    ruoli: tuple[str, ...]
    reparto: Reparto

    @property
    def etichetta(self) -> str:
        return "/".join(self.ruoli)


@dataclass(frozen=True)
class Modulo:
    """Un modulo e i posti che apre in ogni reparto."""

    nome: str
    difensori: int
    centrocampisti: int
    attaccanti: int
    caselle: tuple[Casella, ...] = ()

    @property
    def ufficiale(self) -> bool:
        """Se le sue caselle vengono dallo schema ufficiale o sono dedotte."""
        return bool(caselle_di(self.nome))

    @property
    def reparti(self) -> tuple[tuple[Reparto, int], ...]:
        return (
            (Reparto.PORTA, 1),
            (Reparto.DIFESA, self.difensori),
            (Reparto.CENTROCAMPO, self.centrocampisti),
            (Reparto.ATTACCO, self.attaccanti),
        )

    @property
    def totale(self) -> int:
        return 1 + self.difensori + self.centrocampisti + self.attaccanti


def leggi_modulo(nome: str) -> Modulo:
    """Da «3-4-1-2» al modulo. I reparti intermedi finiscono a centrocampo.

    Un modulo a quattro numeri come 3-4-1-2 ha difesa, centrocampo, trequarti e
    attacco: il trequartista e' un centrocampista avanzato, quindi il suo posto
    si somma al centrocampo. Il reparto di attacco resta l'ultimo numero.
    """
    numeri = [int(n) for n in re.findall(r"\d+", str(nome))]
    if len(numeri) < 3:
        raise FormazioneNonValida(
            f"«{nome}» non e' un modulo: servono almeno tre numeri, come 4-4-2 o 3-4-1-2."
        )
    difensori = numeri[0]
    attaccanti = numeri[-1]
    centrocampisti = sum(numeri[1:-1])
    modulo = Modulo(
        str(nome),
        difensori,
        centrocampisti,
        attaccanti,
        caselle=_caselle_del_modulo(str(nome), difensori, centrocampisti, attaccanti),
    )
    if modulo.totale != TITOLARI:
        raise FormazioneNonValida(
            f"Il modulo «{nome}» mette in campo {modulo.totale} giocatori "
            f"contando il portiere, e devono essere {TITOLARI}."
        )
    return modulo


def _caselle_del_modulo(
    nome: str, difensori: int, centrocampisti: int, attaccanti: int
) -> tuple[Casella, ...]:
    """Le caselle dello schema ufficiale, o quelle dedotte dai reparti.

    Quando il modulo sta nello schema ufficiale si usano i suoi ruoli esatti.
    Per gli altri — i moduli Classic, e i Mantra che non abbiamo ancora
    trascritto — la casella ammette tutti i ruoli del reparto: e' la vecchia
    approssimazione, che resta buona per non rifiutare formazioni lecite.
    """
    ufficiali = caselle_di(nome)
    if ufficiali:
        reparti = [
            Reparto.PORTA,
            *[Reparto.DIFESA] * difensori,
            *[Reparto.CENTROCAMPO] * centrocampisti,
            *[Reparto.ATTACCO] * attaccanti,
        ]
        return tuple(
            Casella(ruoli, reparto)
            for ruoli, reparto in zip(ufficiali, reparti, strict=True)
        )
    return tuple(
        Casella(reparto.ruoli, reparto)
        for reparto, quanti in (
            (Reparto.PORTA, 1),
            (Reparto.DIFESA, difensori),
            (Reparto.CENTROCAMPO, centrocampisti),
            (Reparto.ATTACCO, attaccanti),
        )
        for _ in range(quanti)
    )


@dataclass(frozen=True)
class Formazione:
    """Chi gioca, chi sta fuori, e con che modulo.

    `titolari` e `panchina` sono id di giocatori, **in ordine**: la panchina
    conta, perche' le sostituzioni automatiche pescano da li' dall'alto.
    """

    squadra_id: int
    giornata: int
    modulo: str
    titolari: tuple[int, ...] = ()
    panchina: tuple[int, ...] = ()
    competizione: str = "CAMPIONATO"
    aggiornata_il: str = ""
    # Il portiere d'emergenza del Lodo Messina, se quella giornata ha giocato
    # lui. Sta **sulla formazione** e non solo sulla rosa di proposito: lo
    # stato della rosa cambia appena un portiere torna disponibile, e se il
    # malus dipendesse da quello, ricalcolare una giornata vecchia darebbe un
    # punteggio diverso da quello con cui la partita e' finita.
    portiere_emergenza: int | None = None


def esito_casella(casella: Casella, ruoli_giocatore, modulo: str = "") -> Esito:
    """Cosa succede se quel giocatore occupa quella casella: gratis, col malus,
    o per niente.

    Lo decide la tabella Mantra. Ne escono da sole regole che altrimenti
    andrebbero scritte a mano: il portiere non si adatta mai, e verso l'attacco
    non si sale — un difensore puo' giocare piu' avanti pagando, una punta non
    puo' arretrare in difesa.
    """
    return esito_in_casella(casella.ruoli, ruoli_giocatore, modulo)


def puo_occupare(casella: Casella, ruoli_giocatore, modulo: str = "") -> bool:
    """Se quel giocatore puo' stare li', anche adattandosi e pagando il malus."""
    return esito_casella(casella, ruoli_giocatore, modulo).possibile


def valida(
    formazione: Formazione,
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    in_rosa: set[int],
    modalita: ModalitaSostituzioni = ModalitaSostituzioni.BASIC,
) -> list[str]:
    """Tutto quel che non va nella formazione. Lista vuota = si puo' schierare.

    Torna **tutti** i problemi, non il primo: chi sta schierando vuole sapere
    quante cose deve sistemare, non scoprirle una alla volta.

    Il fuori posizione e' un errore solo in **Easy**: nelle altre modalita' e'
    una scelta lecita che costa il malus, e a dirlo e' `adattamenti()`, non
    un divieto.
    """
    problemi: list[str] = []

    try:
        modulo = leggi_modulo(formazione.modulo)
    except FormazioneNonValida as errore:
        return [str(errore)]

    if len(formazione.titolari) != TITOLARI:
        problemi.append(
            f"Servono {TITOLARI} titolari, ne hai schierati {len(formazione.titolari)}."
        )

    tutti = list(formazione.titolari) + list(formazione.panchina)
    ripetuti = sorted({g for g in tutti if tutti.count(g) > 1})
    if ripetuti:
        problemi.append(
            f"{len(ripetuti)} giocatori compaiono due volte fra titolari e "
            f"panchina: ognuno puo' stare in un posto solo."
        )

    fuori_rosa = [g for g in tutti if g not in in_rosa]
    if fuori_rosa:
        problemi.append(
            f"{len(fuori_rosa)} giocatori schierati non sono in rosa. "
            f"Puo' succedere dopo uno scambio: rifai la formazione."
        )

    if len(formazione.titolari) == TITOLARI and not fuori_rosa and not ripetuti:
        problemi += _problemi_di_reparto(
            formazione, modulo, ruoli_per_giocatore, modalita
        )

    return problemi


def caselle_e_titolari(
    formazione: Formazione,
) -> list[tuple[Casella, int]]:
    """Le caselle del modulo accoppiate a chi le occupa, in ordine.

    Se la formazione e' piu' corta del modulo si torna quel che c'e': serve
    anche mentre la si sta ancora componendo.
    """
    modulo = leggi_modulo(formazione.modulo)
    return list(zip(modulo.caselle, formazione.titolari, strict=False))


# Quanto costa una casella, per scegliere la disposizione migliore. Il
# divieto non e' «infinito»: e' tanto caro da non sceglierlo mai se esiste
# un'alternativa, ma lascia una risposta anche quando alternative non ce ne
# sono — meglio una disposizione imperfetta che nessuna.
_COSTO_VIETATO = 1000
_COSTO = {Esito.LIBERA: 0, Esito.MALUS: 1, Esito.VIETATA: _COSTO_VIETATO}


def _disposizione_migliore(
    modulo: str,
    giocatori: Sequence[int],
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
) -> tuple[int, tuple[int, ...]]:
    """La disposizione che costa meno, col suo costo in malus.

    Il costo serve anche a decidere i cambi: una squadra in cui il subentrato
    non sta in piedi ha dentro almeno un `_COSTO_VIETATO`, e si vede dal
    numero senza doverla guardare casella per casella.
    """
    caselle = leggi_modulo(modulo).caselle
    scelti = list(giocatori)
    if len(scelti) != len(caselle):
        return 0, tuple(scelti)

    costi = [
        [
            _COSTO[esito_casella(casella, ruoli_per_giocatore.get(g, ()), modulo)]
            for g in scelti
        ]
        for casella in caselle
    ]

    # Programmazione dinamica sui sottoinsiemi: undici caselle per 2^11 stati
    # sono poche migliaia di passi, e la risposta e' la migliore in assoluto,
    # non la prima che capita.
    migliore: dict[int, tuple[int, tuple[int, ...]]] = {0: (0, ())}
    for riga in costi:
        prossimo: dict[int, tuple[int, tuple[int, ...]]] = {}
        for usati, (costo, disposizione) in migliore.items():
            for indice_giocatore, costo_casella in enumerate(riga):
                bit = 1 << indice_giocatore
                if usati & bit:
                    continue
                nuovo_costo = costo + costo_casella
                chiave = usati | bit
                if chiave not in prossimo or nuovo_costo < prossimo[chiave][0]:
                    prossimo[chiave] = (nuovo_costo, (*disposizione, indice_giocatore))
        migliore = prossimo

    costo, disposizione = migliore[(1 << len(scelti)) - 1]
    return costo, tuple(scelti[i] for i in disposizione)


def disponi_in_caselle(
    modulo: str,
    giocatori: Sequence[int],
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
) -> tuple[int, ...]:
    """Gli stessi undici, messi nelle caselle che costano meno malus.

    Serve quando l'ordine in cui arrivano **non e' una scelta**: il tabellino
    della piattaforma elenca i titolari nel suo ordine, non nel nostro, e
    accoppiarli alle caselle uno per uno darebbe malus che nessuno ha pagato
    — o un divieto al posto di un punteggio pieno.

    Chi invece la formazione la compone sul sito sceglie la casella da se', e
    quella scelta non si tocca: li' l'ordine e' informazione, qui no.
    """
    return _disposizione_migliore(modulo, giocatori, ruoli_per_giocatore)[1]


def adattamenti(
    formazione: Formazione,
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
) -> list[tuple[int, Casella]]:
    """Chi, fra i titolari, sta giocando in una casella che non e' la sua.

    Non e' un errore: e' un'informazione che chi schiera deve avere prima di
    salvare, perche' ognuno di questi costa il malus di adattamento.
    """
    return [
        (giocatore, casella)
        for casella, giocatore in caselle_e_titolari(formazione)
        if esito_casella(
            casella, ruoli_per_giocatore.get(giocatore, ()), formazione.modulo
        )
        is Esito.MALUS
    ]


def _problemi_di_reparto(
    formazione: Formazione,
    modulo: Modulo,
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    modalita: ModalitaSostituzioni = ModalitaSostituzioni.BASIC,
) -> list[str]:
    """I titolari, nell'ordine, devono stare nelle caselle del modulo.

    Due divieti diversi: quel che la tabella Mantra chiude non si apre in
    nessun modo, e in piu', in modalita' Easy, non si adatta nemmeno chi
    potrebbe pagando.
    """
    problemi = []
    for posizione, (casella, giocatore) in enumerate(
        zip(modulo.caselle, formazione.titolari, strict=False), start=1
    ):
        ruoli = ruoli_per_giocatore.get(giocatore, ())
        esito = esito_casella(casella, ruoli, modulo.nome)
        if esito is Esito.LIBERA:
            continue
        scritti = "/".join(ruoli) or "?"
        dove = f"la casella «{casella.etichetta}» in {casella.reparto.etichetta.lower()}"
        if esito is Esito.VIETATA:
            tocca_la_porta = casella.reparto is Reparto.PORTA or any(
                r in Reparto.PORTA.ruoli for r in ruoli
            )
            perche = (
                "nel Mantra il portiere non si adatta mai"
                if tocca_la_porta
                else "la tabella Mantra non lo consente, perche' un posto si "
                "copre con la stessa linea o con una piu' arretrata, mai con "
                "una piu' avanzata"
            )
            problemi.append(
                f"Il giocatore in posizione {posizione} ha ruolo {scritti} e "
                f"non puo' occupare {dove}: {perche}."
            )
        elif modalita is ModalitaSostituzioni.EASY:
            problemi.append(
                f"Il giocatore in posizione {posizione} ha ruolo {scritti} e "
                f"in {dove} andrebbe adattato: in modalita' Easy nessuno gioca "
                f"fuori posizione."
            )
    return problemi


def schieramento(
    formazione: Formazione,
) -> list[tuple[Reparto, list[int]]]:
    """I titolari divisi per reparto, per disegnarli sul campo.

    Se la formazione non e' completa si mostra quel che c'e': serve anche
    mentre la si sta ancora componendo.
    """
    modulo = leggi_modulo(formazione.modulo)
    righe: list[tuple[Reparto, list[int]]] = []
    posizione = 0
    for reparto, quanti in modulo.reparti:
        fetta = list(formazione.titolari[posizione : posizione + quanti])
        righe.append((reparto, fetta))
        posizione += quanti
    return righe


# --- il blocco --------------------------------------------------------------

MINUTI_DI_ANTICIPO = 1


@dataclass(frozen=True)
class StatoBlocco:
    """Se si puo' ancora schierare, e quanto manca."""

    modificabile: bool
    inizio: datetime | None
    mancano: timedelta | None

    @property
    def motivo(self) -> str:
        if self.modificabile:
            return ""
        if self.inizio is None:
            return "La giornata non ha un orario d'inizio, quindi e' gia' chiusa."
        return (
            f"La giornata e' cominciata alle "
            f"{self.inizio.strftime('%H:%M di %d/%m')}: le formazioni si "
            f"bloccano un minuto prima."
        )


def stato_blocco(
    inizio: datetime | None,
    adesso: datetime | None = None,
    anticipo_minuti: int = MINUTI_DI_ANTICIPO,
) -> StatoBlocco:
    """Le formazioni si chiudono `anticipo_minuti` prima del calcio d'inizio.

    Senza un orario d'inizio non si blocca niente: una giornata senza data e'
    una giornata che non e' stata programmata, e impedire di schierare sarebbe
    peggio che permetterlo.
    """
    adesso = adesso or datetime.now()
    if inizio is None:
        return StatoBlocco(True, None, None)
    limite = inizio - timedelta(minutes=anticipo_minuti)
    if adesso >= limite:
        return StatoBlocco(False, inizio, None)
    return StatoBlocco(True, inizio, limite - adesso)


# --- i voti -----------------------------------------------------------------


@dataclass(frozen=True)
class Voto:
    """La prestazione di un giocatore in una giornata.

    `voto` a None vuol dire **senza voto**: non ha giocato, o non gli e' stato
    assegnato. E' diverso da zero, e fa scattare la sostituzione.
    """

    giocatore_id: int
    giornata: int
    voto: float | None = None
    gol: int = 0
    gol_su_rigore: int = 0
    rigori_sbagliati: int = 0
    rigori_parati: int = 0
    autogol: int = 0
    assist: int = 0
    ammonizioni: int = 0
    espulsioni: int = 0
    gol_subiti: int = 0
    imbattuto: bool = False

    @property
    def ha_giocato(self) -> bool:
        return self.voto is not None


def punteggio_giocatore(voto: Voto, bonus: Bonus) -> float:
    """Voto piu' bonus e malus. Chi non ha giocato non fa punti."""
    if voto.voto is None:
        return 0.0
    return (
        voto.voto
        + voto.gol * bonus.gol_segnato
        + voto.gol_su_rigore * bonus.gol_su_rigore
        + voto.rigori_sbagliati * bonus.rigore_sbagliato
        + voto.rigori_parati * bonus.rigore_parato
        + voto.autogol * bonus.autogol
        + voto.assist * bonus.assist
        + voto.ammonizioni * bonus.ammonizione
        + voto.espulsioni * bonus.espulsione
        + voto.gol_subiti * bonus.gol_subito
        + (bonus.portiere_imbattuto if voto.imbattuto else 0.0)
    )


# --- le sostituzioni --------------------------------------------------------

SOSTITUZIONI_MASSIME = 3


@dataclass
class Sostituzione:
    """Chi e' entrato al posto di chi, e in che reparto."""

    uscito: int
    entrato: int
    reparto: Reparto
    adattato: bool = False


@dataclass
class TabellinoSquadra:
    """Come si e' formato il punteggio di una squadra in una giornata."""

    squadra_id: int
    giornata: int
    schierati: list[tuple[Reparto, int, float]] = field(default_factory=list)
    sostituzioni: list[Sostituzione] = field(default_factory=list)
    # Lo schema con cui si e' giocato davvero: puo' non essere quello scelto,
    # se per far entrare qualcuno la squadra ha dovuto cambiarlo.
    modulo: str = ""
    senza_voto: list[int] = field(default_factory=list)
    # Chi ha giocato in un posto che non e' suo, titolare o subentrato: il
    # punteggio lo dice gia', ma per spiegarlo serve saperlo a parte.
    adattati: list[int] = field(default_factory=list)
    malus_adattamento: float = 0.0
    # Il malus del portiere d'emergenza (Lodo Messina bis), tenuto separato da
    # quello di adattamento: chi legge il tabellino deve capire da dove arriva
    # il punto in meno, e «fuori ruolo» su un portiere in porta sarebbe falso.
    malus_emergenza: float = 0.0
    modificatore_difesa: float = 0.0
    totale: float = 0.0
    gol: int = 0

    @property
    def somma_voti(self) -> float:
        return round(self.totale - self.modificatore_difesa, 2)


def _formazione_effettiva(
    formazione: Formazione,
    voti: dict[int, Voto],
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    disponibili: list[int],
    modalita: ModalitaSostituzioni,
    sostituzioni_massime: int,
    moduli_ammessi: tuple[str, ...],
) -> tuple[str, list[int], list[tuple[int, int]]]:
    """Chi scende davvero in campo: schema, undici e cambi fatti.

    Il criterio non e' «chi copre la casella lasciata libera» ma **se la
    squadra sta ancora in piedi** con quel panchinaro dentro: la piattaforma
    dopo un cambio ridispone tutti, quindi un centrocampista centrale puo'
    entrare al posto di un esterno basso e gli altri si spostano di una
    casella. Chiedere che il subentrato occupi proprio quel posto faceva
    entrare qualcun altro, piu' in basso in panchina.
    """
    schema = formazione.modulo
    effettivi = list(formazione.titolari)
    entrate: list[tuple[int, int]] = []
    usati: set[int] = set()

    for posizione, giocatore in enumerate(formazione.titolari):
        voto = voti.get(giocatore)
        if voto is not None and voto.ha_giocato:
            continue
        if len(entrate) >= sostituzioni_massime:
            continue
        candidati = [g for g in disponibili if g not in usati]
        scelta = _chi_entra(
            effettivi,
            posizione,
            candidati,
            ruoli_per_giocatore,
            modalita,
            schema,
            moduli_ammessi,
            uscito=giocatore,
        )
        if scelta is None:
            continue
        entrato, schema = scelta
        effettivi[posizione] = entrato
        usati.add(entrato)
        entrate.append((giocatore, entrato))

    return schema, effettivi, entrate


def calcola_squadra(
    formazione: Formazione,
    voti: dict[int, Voto],
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    parametri: ParametriLega,
    bonus: Bonus | None = None,
    fasce_difesa: tuple[FasciaModificatore, ...] = (),
    sostituzioni_massime: int = SOSTITUZIONI_MASSIME,
    modalita: ModalitaSostituzioni = ModalitaSostituzioni.BASIC,
    moduli_ammessi: Sequence[str] = (),
) -> TabellinoSquadra:
    """Il punteggio di una squadra: sostituzioni, adattamenti, modificatore, gol.

    Chi non ha voto viene rimpiazzato secondo la modalita' scelta dalla lega
    (`ModalitaSostituzioni`): cambia chi entra, non quante sostituzioni si
    possono fare. Chi gioca in un posto che non e' suo — subentrato o
    titolare — paga il malus di adattamento. Finiti i cambi disponibili, chi
    resta senza voto vale zero.

    Il portiere si trova per primo perche' e' il primo posto del modulo: e'
    anche la regola Mantra, che lo sostituisce prima di chiunque altro.

    Con `moduli_ammessi` si accende il **cambio modulo**: quando nessuno in
    panchina sta in piedi nello schema scelto, si prova a passare a un altro
    schema della lega pur di far entrare qualcuno. E' l'ultima risorsa, dopo
    aver guardato tutta la panchina nel modulo di partenza.
    """
    bonus = bonus or Bonus()
    tabellino = TabellinoSquadra(formazione.squadra_id, formazione.giornata)
    malus = abs(parametri.malus_adattamento)
    emergenza = formazione.portiere_emergenza

    disponibili = [g for g in formazione.panchina if g in voti and voti[g].ha_giocato]
    schema, effettivi, entrate = _formazione_effettiva(
        formazione,
        voti,
        ruoli_per_giocatore,
        disponibili,
        modalita,
        sostituzioni_massime,
        tuple(moduli_ammessi or ()),
    )
    tabellino.modulo = schema
    tabellino.senza_voto = [
        g for g in formazione.titolari if not (g in voti and voti[g].ha_giocato)
    ]

    # Dopo un cambio la squadra si ridispone: e' quello che fa la piattaforma,
    # ed e' il motivo per cui un centrocampista puo' entrare al posto di un
    # esterno basso — gli altri si spostano di una casella. Senza sostituzioni
    # resta l'ordine scelto da chi ha schierato, che li' e' una scelta sua.
    if entrate or schema != formazione.modulo:
        effettivi = list(disponi_in_caselle(schema, effettivi, ruoli_per_giocatore))

    def registra(casella: Casella, giocatore: int) -> bool:
        """Mette in campo chi puo' starci, e segna se ha dovuto adattarsi.

        Torna False quando quella casella non lo ammette proprio: allora vale
        zero. Non e' un dettaglio da arrotondare — e' una formazione che non
        si sarebbe potuta schierare.
        """
        esito = esito_casella(casella, ruoli_per_giocatore.get(giocatore, ()), schema)
        vietato = esito is Esito.VIETATA or (
            modalita is ModalitaSostituzioni.EASY and esito is not Esito.LIBERA
        )
        if vietato:
            tabellino.schierati.append((casella.reparto, giocatore, 0.0))
            return False

        punti = punteggio_giocatore(voti[giocatore], bonus)
        if esito is Esito.MALUS:
            punti = round(punti - malus, 2)
            tabellino.adattati.append(giocatore)
            tabellino.malus_adattamento = round(tabellino.malus_adattamento - malus, 2)
        # Lodo Messina bis: il portiere d'emergenza paga lo stesso malus di
        # chi gioca fuori ruolo, pur essendo in porta e portiere di ruolo.
        # Si somma a quello di adattamento invece di sostituirlo: sono due
        # cose diverse, e nessuna delle due esclude l'altra.
        if giocatore == emergenza:
            punti = round(punti - malus, 2)
            tabellino.malus_emergenza = round(tabellino.malus_emergenza - malus, 2)
        tabellino.schierati.append((casella.reparto, giocatore, punti))
        return esito is Esito.MALUS

    caselle = leggi_modulo(schema).caselle
    entrati = dict(entrate)
    per_giocatore = {entrato: uscito for uscito, entrato in entrate}
    for casella, giocatore in zip(caselle, effettivi, strict=False):
        voto = voti.get(giocatore)
        if voto is None or not voto.ha_giocato:
            # Nessuno ha potuto coprirlo: resta in campo e vale zero.
            tabellino.schierati.append((casella.reparto, giocatore, 0.0))
            continue

        adattato = registra(casella, giocatore)
        if giocatore in per_giocatore:
            tabellino.sostituzioni.append(
                Sostituzione(
                    per_giocatore[giocatore],
                    giocatore,
                    casella.reparto,
                    adattato=adattato,
                )
            )
    del entrati

    tabellino.modificatore_difesa = (
        _modificatore_difesa(
            tabellino, voti, fasce_difesa, ruoli_per_giocatore, parametri
        )
        if parametri.modificatore_difesa and fasce_difesa
        else 0.0
    )
    tabellino.totale = round(
        sum(p for _, _, p in tabellino.schierati) + tabellino.modificatore_difesa, 2
    )
    tabellino.gol = fasce_gol(tabellino.totale, parametri)
    return tabellino


def _chi_entra(
    effettivi: list[int],
    posizione: int,
    candidati: list[int],
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    modalita: ModalitaSostituzioni,
    modulo: str,
    moduli_ammessi: tuple[str, ...] = (),
    uscito: int | None = None,
) -> tuple[int, str] | None:
    """Chi entra e con che schema. `None` se non entra nessuno.

    Si guarda **la squadra intera**, non la casella rimasta vuota: entra chi
    lascia in piedi una formazione schierabile, e a disporla ci pensa poi
    `disponi_in_caselle`. E' il motivo per cui un centrocampista puo' entrare
    al posto di un esterno basso — gli altri si spostano — e la regola che la
    piattaforma applica davvero.

    Prima di tutto viene la **sostituzione diretta**: se in panchina c'e'
    qualcuno con lo **stesso ruolo esatto** di chi esce — «M/C» per un «M/C»,
    non un «C/T» — entra lui, anche se sta piu' in basso. E' la prima regola
    della formula Basic, e si vede nei tabellini: a un M/C senza voto la
    piattaforma ha preferito il sesto di panchina, che era M/C, al quarto,
    che era C/T.

    Poi le modalita' scelgono *fra* i possibili:

    - **Easy**: solo chi non costa nessun malus a nessuno.
    - **Basic**: prima chi costa meno, a parita' l'ordine di panchina.
    - **Master**: il primo della panchina fra quelli che stanno in piedi,
      pagando se serve.

    Il **cambio modulo** e' l'ultima risorsa: prima si guarda tutta la
    panchina nello schema scelto dal fantallenatore, e solo se non entra
    nessuno si provano gli altri schemi della lega, nell'ordine in cui la
    lega li elenca.
    """

    def prova_con(candidato: int, schema: str) -> tuple[int, bool] | None:
        """Quanto costa farlo entrare, e se **lui** gioca nel suo ruolo.

        Le due cose sono diverse: la squadra puo' costare un malus perche' si
        adatta un altro, e a Easy interessa solo che non si adatti chi entra.
        """
        prova = list(effettivi)
        prova[posizione] = candidato
        costo, disposti = _disposizione_migliore(schema, prova, ruoli_per_giocatore)
        if costo >= _COSTO_VIETATO:
            return None
        caselle = leggi_modulo(schema).caselle
        sua = next(c for c, g in zip(caselle, disposti, strict=True) if g == candidato)
        esito = esito_casella(sua, ruoli_per_giocatore.get(candidato, ()), schema)
        return costo, esito is Esito.LIBERA

    altri = tuple(m for m in moduli_ammessi if m != modulo)
    for schema in (modulo, *altri):
        prove = [(g, prova_con(g, schema)) for g in candidati]
        possibili = [
            (g, costo, suo) for g, prova in prove if prova for costo, suo in [prova]
        ]
        if modalita is ModalitaSostituzioni.EASY:
            possibili = [(g, c, suo) for g, c, suo in possibili if suo]
        if not possibili:
            continue
        if modalita is ModalitaSostituzioni.MASTER:
            return possibili[0][0], schema
        suoi_ruoli = frozenset(ruoli_per_giocatore.get(uscito, ()) if uscito else ())
        uguale = [
            g
            for g, _, _ in possibili
            if suoi_ruoli and frozenset(ruoli_per_giocatore.get(g, ())) == suoi_ruoli
        ]
        if uguale:
            return uguale[0], schema
        minimo = min(c for _, c, _ in possibili)
        return next(g for g, c, _ in possibili if c == minimo), schema
    return None


def _modificatore_difesa(
    tabellino: TabellinoSquadra,
    voti: dict[int, Voto],
    fasce: tuple[FasciaModificatore, ...],
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    parametri: ParametriLega,
) -> float:
    """Media di portiere e migliori difensori, tradotta in bonus.

    Due cose non si indovinano e le hanno dette i tabellini veri (vedi
    PUNTI_APERTI.md, punto 21):

    - si usa il **voto puro**, senza bonus e malus: il modificatore premia la
      prestazione della difesa, non i gol che i difensori hanno segnato;
    - difensore e' chi **ha il ruolo** di difensore, non chi occupa una
      casella della linea arretrata. Gli esterni contano: in un 3-4-x i due
      `E` sono i quinti di centrocampo, stanno in una casella di centrocampo,
      e la piattaforma li mette lo stesso nella media. Contando per casella,
      otto squadre su dieci prendevano il bonus sbagliato.
    """
    pescabili = [
        voti[g].voto
        for _, g, _ in tabellino.schierati
        if g in voti
        and voti[g].voto is not None
        and set(ruoli_per_giocatore.get(g, ())) & set(RUOLI_DIFENSIVI)
    ]
    portiere = [
        voti[g].voto
        for reparto, g, _ in tabellino.schierati
        if reparto is Reparto.PORTA and g in voti and voti[g].voto is not None
    ]
    quanti = max(1, parametri.modificatore_difensori)
    difensori = sorted(pescabili, reverse=True)[:quanti]
    if len(difensori) < quanti:
        return 0.0
    if parametri.modificatore_con_portiere:
        if not portiere:
            return 0.0
        difensori = [portiere[0], *difensori]
    return bonus_modificatore(sum(difensori) / len(difensori), fasce)


@dataclass(frozen=True)
class EsitoPartita:
    """Il risultato di uno scontro diretto, con i due tabellini."""

    casa: TabellinoSquadra
    trasferta: TabellinoSquadra

    @property
    def punteggio(self) -> str:
        return f"{self.casa.gol}-{self.trasferta.gol}"


def calcola_partita(
    formazione_casa: Formazione,
    formazione_trasferta: Formazione,
    voti: dict[int, Voto],
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    parametri: ParametriLega,
    bonus: Bonus | None = None,
    fasce_difesa: tuple[FasciaModificatore, ...] = (),
    sostituzioni_massime: int = SOSTITUZIONI_MASSIME,
    modalita: ModalitaSostituzioni = ModalitaSostituzioni.BASIC,
    moduli_ammessi: Sequence[str] = (),
) -> EsitoPartita:
    """Uno scontro diretto: due tabellini e il punteggio in gol."""
    comuni = {
        "voti": voti,
        "ruoli_per_giocatore": ruoli_per_giocatore,
        "parametri": parametri,
        "bonus": bonus,
        "fasce_difesa": fasce_difesa,
        "sostituzioni_massime": sostituzioni_massime,
        "modalita": modalita,
        "moduli_ammessi": moduli_ammessi,
    }
    return EsitoPartita(
        calcola_squadra(formazione_casa, **comuni),
        calcola_squadra(formazione_trasferta, **comuni),
    )


def frase_adattamenti(quanti: int, malus: float) -> str:
    """«Un adattamento: 1 punto in meno», al plurale solo quando serve.

    La frase sta qui e non nelle pagine perche' e' la stessa in tutte: la
    scriveva la vista Streamlit, la riscriveva l'API, e in tutte e due diceva
    «1 punti in meno». Una copia si corregge sempre per prima.

    Il singolare guarda il **costo**, non il numero di adattati: con un malus
    da mezzo punto, due adattamenti fanno «1 punto in meno».
    """
    if quanti <= 0:
        return ""
    costo = abs(malus) * quanti
    quanto = f"{costo:g} {'punto' if costo == 1 else 'punti'} in meno"
    if quanti == 1:
        return f"Un adattamento: {quanto}."
    return f"{quanti} adattamenti: {quanto}."


def formazione_suggerita(
    squadra_id: int,
    giornata: int,
    modulo: str,
    rosa: list[int],
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    panchinari: int | None = None,
) -> Formazione:
    """Una formazione di partenza valida, da correggere invece che comporre.

    Non e' una scelta tecnica: prende il primo giocatore che puo' occupare
    ogni posto. Serve a chi apre la pagina e trova undici caselle vuote.

    `panchinari` taglia la panchina al numero che la lega ammette: una rosa da
    trenta non entra in una panchina da dodici, e una proposta piu' lunga del
    consentito nasce gia' da correggere.
    """
    schema = leggi_modulo(modulo)
    liberi = list(rosa)
    titolari: list[int] = []
    for casella in schema.caselle:
        for cerca_gratis in (True, False):
            # Prima chi la casella ammette di suo, poi — se proprio non c'e'
            # nessuno — chi ci starebbe adattandosi. Una proposta con un
            # adattamento e' meglio di una casella vuota, ma resta l'ultima
            # scelta: chi apre la pagina non deve trovarsi un malus regalato.
            scelto = next(
                (
                    g
                    for g in liberi
                    if g not in titolari
                    and (
                        esito_casella(casella, ruoli_per_giocatore.get(g, ()), modulo)
                        is Esito.LIBERA
                        if cerca_gratis
                        else puo_occupare(casella, ruoli_per_giocatore.get(g, ()), modulo)
                    )
                ),
                None,
            )
            if scelto is not None:
                break
        if scelto is not None:
            titolari.append(scelto)
            liberi.remove(scelto)
    panchina = tuple(g for g in rosa if g not in titolari)
    if panchinari is not None:
        panchina = panchina[: max(0, panchinari)]
    return Formazione(
        squadra_id=squadra_id,
        giornata=giornata,
        modulo=modulo,
        titolari=tuple(titolari),
        panchina=panchina,
    )
