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
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .leghe import (
    Bonus,
    FasciaModificatore,
    ModalitaSostituzioni,
    bonus_modificatore,
)
from .mantra import Esito, esito_effettivo
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


# I ruoli di confine valgono in due reparti: l'esterno «E» fa il terzino o
# l'ala di centrocampo, l'ala «W» e il trequartista «T» giocano avanzati o in
# mezzo. E' il motivo per cui i reparti sopra si sovrappongono.
RUOLI_DI_CONFINE = ("E", "W", "T")

TITOLARI = 11


@dataclass(frozen=True)
class Modulo:
    """Un modulo e i posti che apre in ogni reparto."""

    nome: str
    difensori: int
    centrocampisti: int
    attaccanti: int

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
    modulo = Modulo(str(nome), difensori, centrocampisti, attaccanti)
    if modulo.totale != TITOLARI:
        raise FormazioneNonValida(
            f"Il modulo «{nome}» mette in campo {modulo.totale} giocatori "
            f"contando il portiere, e devono essere {TITOLARI}."
        )
    return modulo


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


def esito_reparto(reparto: Reparto, ruoli_giocatore) -> Esito:
    """Cosa succede se quel giocatore occupa un posto in quel reparto.

    Si chiede alla tabella delle sostituzioni del Mantra, prendendo il miglior
    esito fra i ruoli del reparto e quelli del giocatore. Da li' escono da
    sole due regole che altrimenti andrebbero scritte a mano: il portiere non
    si adatta mai, e verso l'attacco non si sale — un difensore puo' giocare
    piu' avanti pagando, una punta non puo' arretrare in difesa.

    Nota onesta: il reparto e' un'approssimazione della casella esatta del
    modulo, che non abbiamo (vedi PUNTI_APERTI.md). Fra i ruoli del reparto si
    prende il migliore, quindi il sito e' un filo piu' permissivo della
    piattaforma, mai piu' severo.
    """
    return esito_effettivo(reparto.ruoli, ruoli_giocatore)


def puo_occupare(reparto: Reparto, ruoli_giocatore) -> bool:
    """Se quel giocatore puo' stare li', anche adattandosi e pagando il malus."""
    return esito_reparto(reparto, ruoli_giocatore).possibile


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


def adattamenti(
    formazione: Formazione,
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
) -> list[tuple[int, Reparto]]:
    """Chi, fra i titolari, sta giocando in un posto che non e' il suo.

    Non e' un errore: e' un'informazione che chi schiera deve avere prima di
    salvare, perche' ognuno di questi costa il malus di adattamento.
    """
    fuori: list[tuple[int, Reparto]] = []
    for reparto, giocatori in schieramento(formazione):
        for giocatore in giocatori:
            ruoli = ruoli_per_giocatore.get(giocatore, ())
            if esito_reparto(reparto, ruoli) is Esito.MALUS:
                fuori.append((giocatore, reparto))
    return fuori


def _problemi_di_reparto(
    formazione: Formazione,
    modulo: Modulo,
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    modalita: ModalitaSostituzioni = ModalitaSostituzioni.BASIC,
) -> list[str]:
    """I titolari, nell'ordine, devono riempire i posti del modulo.

    Due divieti diversi: la porta non si adatta mai, e in modalita' Easy non
    si adatta nemmeno il resto.
    """
    problemi = []
    posizione = 0
    for reparto, quanti in modulo.reparti:
        for _ in range(quanti):
            giocatore = formazione.titolari[posizione]
            ruoli = ruoli_per_giocatore.get(giocatore, ())
            if reparto.accetta(ruoli):
                posizione += 1
                continue
            if not puo_occupare(reparto, ruoli):
                tocca_la_porta = reparto is Reparto.PORTA or any(
                    r in Reparto.PORTA.ruoli for r in ruoli
                )
                perche = (
                    "nel Mantra il portiere non si adatta mai"
                    if tocca_la_porta
                    else "la tabella Mantra non lo consente, perche' un posto "
                    "si copre con la stessa linea o con una piu' arretrata, "
                    "mai con una piu' avanzata"
                )
                problemi.append(
                    f"Il giocatore in posizione {posizione + 1} ha ruolo "
                    f"{'/'.join(ruoli) or '?'} e non puo' occupare un posto in "
                    f"{reparto.etichetta.lower()}: {perche}."
                )
            elif modalita is ModalitaSostituzioni.EASY:
                problemi.append(
                    f"Il giocatore in posizione {posizione + 1} ha ruolo "
                    f"{'/'.join(ruoli) or '?'} e non puo' occupare un posto "
                    f"in {reparto.etichetta.lower()}: in modalita' Easy "
                    f"nessuno gioca fuori posizione."
                )
            posizione += 1
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
    senza_voto: list[int] = field(default_factory=list)
    # Chi ha giocato in un posto che non e' suo, titolare o subentrato: il
    # punteggio lo dice gia', ma per spiegarlo serve saperlo a parte.
    adattati: list[int] = field(default_factory=list)
    malus_adattamento: float = 0.0
    modificatore_difesa: float = 0.0
    totale: float = 0.0
    gol: int = 0

    @property
    def somma_voti(self) -> float:
        return round(self.totale - self.modificatore_difesa, 2)


def calcola_squadra(
    formazione: Formazione,
    voti: dict[int, Voto],
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    parametri: ParametriLega,
    bonus: Bonus | None = None,
    fasce_difesa: tuple[FasciaModificatore, ...] = (),
    sostituzioni_massime: int = SOSTITUZIONI_MASSIME,
    modalita: ModalitaSostituzioni = ModalitaSostituzioni.BASIC,
) -> TabellinoSquadra:
    """Il punteggio di una squadra: sostituzioni, adattamenti, modificatore, gol.

    Chi non ha voto viene rimpiazzato secondo la modalita' scelta dalla lega
    (`ModalitaSostituzioni`): cambia chi entra, non quante sostituzioni si
    possono fare. Chi gioca in un posto che non e' suo — subentrato o
    titolare — paga il malus di adattamento. Finiti i cambi disponibili, chi
    resta senza voto vale zero.

    Il portiere si trova per primo perche' e' il primo posto del modulo: e'
    anche la regola Mantra, che lo sostituisce prima di chiunque altro.
    """
    bonus = bonus or Bonus()
    tabellino = TabellinoSquadra(formazione.squadra_id, formazione.giornata)
    malus = abs(parametri.malus_adattamento)

    disponibili = [g for g in formazione.panchina if g in voti and voti[g].ha_giocato]
    usati: set[int] = set()

    def punti_di(giocatore: int, reparto: Reparto) -> tuple[float, bool]:
        """Quanto vale, e se ha dovuto adattarsi per stare li'."""
        adattato = (
            esito_reparto(reparto, ruoli_per_giocatore.get(giocatore, ())) is Esito.MALUS
        )
        punti = punteggio_giocatore(voti[giocatore], bonus)
        return (round(punti - malus, 2) if adattato else punti), adattato

    def ammesso(giocatore: int, reparto: Reparto) -> bool:
        """Puo' stare in quel posto, foss'anche adattandosi?

        In Easy si sta solo nel proprio reparto; ovunque, il portiere non si
        adatta mai. Chi non e' ammesso vale zero: non e' un dettaglio da
        arrotondare, e' una formazione che non si sarebbe potuta schierare.
        """
        esito = esito_reparto(reparto, ruoli_per_giocatore.get(giocatore, ()))
        if modalita is ModalitaSostituzioni.EASY:
            return esito is Esito.LIBERA
        return esito.possibile

    def registra(reparto: Reparto, giocatore: int) -> None:
        punti, adattato = punti_di(giocatore, reparto)
        if adattato:
            tabellino.adattati.append(giocatore)
            tabellino.malus_adattamento = round(tabellino.malus_adattamento - malus, 2)
        tabellino.schierati.append((reparto, giocatore, punti))

    for reparto, giocatori in schieramento(formazione):
        for giocatore in giocatori:
            voto = voti.get(giocatore)
            if voto is not None and voto.ha_giocato:
                if not ammesso(giocatore, reparto):
                    tabellino.schierati.append((reparto, giocatore, 0.0))
                    continue
                registra(reparto, giocatore)
                continue

            tabellino.senza_voto.append(giocatore)
            sostituto = (
                _chi_entra(disponibili, usati, giocatore, ruoli_per_giocatore, modalita)
                if len(tabellino.sostituzioni) < sostituzioni_massime
                else None
            )

            if sostituto is None:
                tabellino.schierati.append((reparto, giocatore, 0.0))
                continue

            usati.add(sostituto)
            # Il cambio si valuta fra i due giocatori, non contro il reparto:
            # e' la tabella delle sostituzioni a dire se chi entra si sta
            # adattando, e quindi se paga.
            esito = esito_effettivo(
                ruoli_per_giocatore.get(giocatore, ()),
                ruoli_per_giocatore.get(sostituto, ()),
            )
            adattato = esito is Esito.MALUS
            tabellino.sostituzioni.append(
                Sostituzione(giocatore, sostituto, reparto, adattato=adattato)
            )
            punti = punteggio_giocatore(voti[sostituto], bonus)
            if adattato:
                punti = round(punti - malus, 2)
                tabellino.adattati.append(sostituto)
                tabellino.malus_adattamento = round(
                    tabellino.malus_adattamento - malus, 2
                )
            tabellino.schierati.append((reparto, sostituto, punti))

    tabellino.modificatore_difesa = (
        _modificatore_difesa(tabellino, voti, fasce_difesa)
        if parametri.modificatore_difesa and fasce_difesa
        else 0.0
    )
    tabellino.totale = round(
        sum(p for _, _, p in tabellino.schierati) + tabellino.modificatore_difesa, 2
    )
    tabellino.gol = fasce_gol(tabellino.totale, parametri)
    return tabellino


def _chi_entra(
    disponibili: list[int],
    usati: set[int],
    uscito: int,
    ruoli_per_giocatore: dict[int, tuple[str, ...]],
    modalita: ModalitaSostituzioni,
) -> int | None:
    """Chi entra al posto di chi e' uscito, secondo la modalita' della lega.

    Chi puo' entrare lo dice la **tabella delle sostituzioni** del Mantra, che
    guarda i due ruoli e non il reparto: per coprire una punta si puo' usare
    un difensore pagando, per coprire un difensore non si puo' usare una
    punta, e in porta va solo un portiere. Le modalita' scelgono *fra* i
    possibili:

    - **Easy**: solo chi entra senza malus.
    - **Basic**: prima chi entra senza malus, anche se sta piu' in fondo;
      solo se non c'e' nessuno, il primo che puo' entrare pagando.
    - **Master**: il primo della panchina fra quelli che possono entrare,
      pagando se serve.

    A parita' di condizioni vince sempre l'ordine della panchina: e' la
    volonta' del fantallenatore, non un dettaglio.
    """
    ruoli_uscito = ruoli_per_giocatore.get(uscito, ())
    esiti = [
        (g, esito_effettivo(ruoli_uscito, ruoli_per_giocatore.get(g, ())))
        for g in disponibili
        if g not in usati
    ]
    possibili = [(g, e) for g, e in esiti if e is not Esito.VIETATA]
    senza_malus = [g for g, e in possibili if e is Esito.LIBERA]

    if modalita is ModalitaSostituzioni.EASY:
        return senza_malus[0] if senza_malus else None
    if modalita is ModalitaSostituzioni.MASTER:
        return possibili[0][0] if possibili else None
    if senza_malus:
        return senza_malus[0]
    return possibili[0][0] if possibili else None


def _modificatore_difesa(
    tabellino: TabellinoSquadra,
    voti: dict[int, Voto],
    fasce: tuple[FasciaModificatore, ...],
) -> float:
    """Media di portiere e tre migliori difensori, tradotta in bonus.

    Si usa il **voto puro**, senza bonus e malus: il modificatore premia la
    prestazione della difesa, non i gol che i difensori hanno segnato.
    """
    portiere = [
        voti[g].voto
        for reparto, g, _ in tabellino.schierati
        if reparto is Reparto.PORTA and g in voti and voti[g].voto is not None
    ]
    difensori = sorted(
        (
            voti[g].voto
            for reparto, g, _ in tabellino.schierati
            if reparto is Reparto.DIFESA and g in voti and voti[g].voto is not None
        ),
        reverse=True,
    )
    if not portiere or len(difensori) < 3:
        return 0.0
    media = (portiere[0] + sum(difensori[:3])) / 4
    return bonus_modificatore(media, fasce)


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
    }
    return EsitoPartita(
        calcola_squadra(formazione_casa, **comuni),
        calcola_squadra(formazione_trasferta, **comuni),
    )


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
    for reparto, quanti in schema.reparti:
        for _ in range(quanti):
            scelto = next(
                (
                    g
                    for g in liberi
                    if reparto.accetta(ruoli_per_giocatore.get(g, ()))
                    and g not in titolari
                ),
                None,
            )
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
