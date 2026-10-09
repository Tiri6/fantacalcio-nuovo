"""Le competizioni della lega: campionato, Coppa Italia, F1 Rush, albo d'oro.

Una lega non e' solo il campionato. Qui stanno le regole di chi si affronta e
quando, e il registro di chi ha vinto cosa.

Il campionato c'e' sempre; coppa e F1 Rush si accendono creando la lega. Non
e' una preferenza estetica: una lega senza coppa non deve vedere pagine che
parlano di una competizione che non gioca.

La **Supercoppa non esiste piu'**: il V3 l'ha sostituita con la *F1 Rush
Finale*, sulle ultime sei giornate di Serie A. Non e' un cambio di nome — la
Supercoppa era una gara fra due squadre, la F1 Rush e' una classifica a tappe
fra tutte.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import Enum

# Under 21 si valuta al **31 agosto**, uguale tutti gli anni.
#
# L'articolo 2 scrive «alla data del draft di Settembre». La lega ha deciso di
# usare invece una data fissa: cosi' lo status non si sposta se il draft
# slitta, e chi e' Under lo si sa gia' prima di sapere quando si gioca l'asta.
# E' una divergenza voluta dal testo, annotata in PUNTI_APERTI.md perche' alla
# prossima revisione del regolamento venga scritta anche li'.
GIORNO_RIFERIMENTO_U21 = (8, 31)

# Quante giornate ha la Serie A. Non e' un numero del regolamento della lega —
# e' il formato del campionato italiano — ma serve per sapere quali sono «le
# ultime sei giornate» su cui si corre la F1 Rush. Sta qui e non sparso nelle
# pagine: se la Serie A cambiasse formato, si corregge in un punto solo.
GIORNATE_SERIE_A = 38


def data_riferimento_u21(stagione: str) -> date:
    """Il 31 agosto della stagione: da '2026/27' si ricava il 2026.

    Data fissa per scelta della lega (vedi il commento qui sopra): non cambia
    se il draft si sposta. Una stagione scritta male non deve far fallire il
    caricamento di una rosa: in quel caso si usa l'anno corrente, che e'
    l'ipotesi meno sbagliata.
    """
    mese, giorno = GIORNO_RIFERIMENTO_U21
    try:
        anno = int(str(stagione).split("/")[0])
    except (ValueError, AttributeError, IndexError):
        anno = date.today().year
    return date(anno, mese, giorno)


class TipoCompetizione(Enum):
    CAMPIONATO = "Campionato"
    COPPA_ITALIA = "Coppa Italia"
    F1_RUSH = "F1 Rush Finale"

    @property
    def etichetta(self) -> str:
        return self.value

    @property
    def icona(self) -> str:
        return {
            "Campionato": "🏆",
            "Coppa Italia": "🥇",
            "F1 Rush Finale": "🏁",
        }[self.value]


class FormatoCoppa(Enum):
    ELIMINAZIONE_SECCA = "Eliminazione diretta, gara secca"
    ANDATA_RITORNO = "Eliminazione diretta, andata e ritorno"
    GIRONI_PIU_SCONTRI = "Gironi, poi eliminazione diretta"

    @property
    def etichetta(self) -> str:
        return self.value


class CriterioF1Rush(Enum):
    """Come si assegnano i punti di ogni tappa della F1 Rush.

    Il V3 dice **solo** che la F1 Rush Finale si disputa nelle ultime sei
    giornate di Serie A: il meccanismo non lo scrive (vedi PUNTI_APERTI.md).
    Il default e' la lettura piu' vicina al nome e alla piattaforma, dove il
    campionato «Formula 1» assegna punti per posizione in ogni giornata.
    """

    PUNTI_PER_POSIZIONE = "Punti per posizione in ogni giornata, come in F1"
    SOMMA_FANTAPUNTI = "Somma dei fantapunti delle sei giornate"

    @property
    def etichetta(self) -> str:
        return self.value


class CompetizioneNonValida(ValueError):
    pass


@dataclass(frozen=True)
class RegoleCoppa:
    """Come si gioca la Coppa Italia.

    I default sono quelli del V3: **due gironi all'italiana con andata e
    ritorno, disputati a fine campionato, seguiti da scontri diretti**. Prima
    la coppa seguiva il formato di Leghe Fantacalcio — eliminazione diretta a
    gara secca intervallata al campionato — e quel formato resta disponibile,
    perche' una lega diversa puo' sceglierlo.

    Con i gironi, `squadre_ammesse` sono quelle che entrano in coppa (dieci,
    cioe' tutte) e non devono essere una potenza di due: a doverlo essere sono
    le **qualificate**, cioe' quelle che arrivano agli scontri diretti.
    """

    formato: FormatoCoppa = FormatoCoppa.GIRONI_PIU_SCONTRI
    squadre_ammesse: int = 10
    gironi: int = 2
    qualificate_per_girone: int = 2
    # Il V3 la mette in coda: «disputati a fine campionato». Con il formato a
    # eliminazione diretta invece i turni si intervallano al campionato, ed e'
    # li' che servono `prima_giornata` e `ogni_quante_giornate`.
    dopo_il_campionato: bool = True
    prima_giornata: int = 5
    ogni_quante_giornate: int = 4
    teste_di_serie: bool = True
    # A parita' di gol vince chi ha totalizzato piu' fantapunti. Senza questa
    # regola una coppa a gara secca non saprebbe chi far passare.
    spareggio_ai_fantapunti: bool = True
    finale_in_campo_neutro: bool = True

    def __post_init__(self) -> None:
        if self.squadre_ammesse < 2:
            raise CompetizioneNonValida("La coppa vuole almeno due squadre")
        if self.a_gironi:
            if self.gironi < 1:
                raise CompetizioneNonValida("Servono almeno un girone")
            if self.squadre_ammesse % self.gironi:
                raise CompetizioneNonValida(
                    f"{self.squadre_ammesse} squadre non si dividono in "
                    f"{self.gironi} gironi uguali"
                )
            if self.qualificate_per_girone < 1:
                raise CompetizioneNonValida(
                    "Da ogni girone deve passare almeno una squadra"
                )
            if self.qualificate_per_girone > self.squadre_per_girone:
                raise CompetizioneNonValida(
                    f"Non possono qualificarsi {self.qualificate_per_girone} "
                    f"squadre da un girone di {self.squadre_per_girone}"
                )
        if self.squadre_a_eliminazione & (self.squadre_a_eliminazione - 1):
            raise CompetizioneNonValida(
                f"Le squadre agli scontri diretti devono essere una potenza di "
                f"due (2, 4, 8, 16): sono {self.squadre_a_eliminazione}"
            )
        if self.prima_giornata < 1:
            raise CompetizioneNonValida("La prima giornata di coppa parte da 1")
        if self.ogni_quante_giornate < 1:
            raise CompetizioneNonValida(
                "Fra un turno di coppa e l'altro serve almeno una giornata"
            )

    @property
    def a_gironi(self) -> bool:
        return self.formato is FormatoCoppa.GIRONI_PIU_SCONTRI

    @property
    def squadre_per_girone(self) -> int:
        return self.squadre_ammesse // max(self.gironi, 1)

    @property
    def squadre_a_eliminazione(self) -> int:
        """Quante arrivano agli scontri diretti."""
        if not self.a_gironi:
            return self.squadre_ammesse
        return self.gironi * self.qualificate_per_girone

    @property
    def giornate_di_girone(self) -> int:
        """Quante giornate dura la fase a gironi: andata e ritorno.

        Zero senza gironi. Con un girone di cinque, ognuno salta un turno e le
        giornate restano quattro per girone — il calendario all'italiana con un
        numero dispari di squadre prevede un riposo a testa.
        """
        if not self.a_gironi:
            return 0
        squadre = self.squadre_per_girone
        return 2 * (squadre - 1 if squadre % 2 == 0 else squadre)

    @property
    def turni(self) -> int:
        """Quanti scontri diretti servono per arrivare alla finale."""
        turni, squadre = 0, self.squadre_a_eliminazione
        while squadre > 1:
            squadre //= 2
            turni += 1
        return turni

    def nome_turno(self, numero: int) -> str:
        """«Ottavi», «Quarti», «Semifinale», «Finale» a seconda di quante restano."""
        rimaste = self.squadre_a_eliminazione // (2 ** (numero - 1))
        return {
            2: "Finale",
            4: "Semifinali",
            8: "Quarti di finale",
            16: "Ottavi di finale",
            32: "Sedicesimi di finale",
        }.get(rimaste, f"{numero}º turno")

    def giornate_dei_turni(self) -> tuple[int, ...]:
        """A quali giornate di campionato cadono i turni di coppa."""
        return tuple(
            self.prima_giornata + self.ogni_quante_giornate * n for n in range(self.turni)
        )


# Punti per posizione di tappa, dal 1o al 10o: e' la scala in vigore in
# Formula 1, e con dieci squadre arriva esattamente in fondo alla griglia.
# E' un'ipotesi, non il regolamento: il V3 non la scrive (PUNTI_APERTI.md).
PUNTI_TAPPA_F1 = (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)


@dataclass(frozen=True)
class RegoleF1Rush:
    """Come si gioca la F1 Rush Finale (art. 1).

    `giornate_serie_a` e' il numero di turni finali di Serie A su cui si
    corre: sei, per il V3. Non e' il numero di giornate di lega — la F1 Rush
    sta **sopra** il campionato, usa gli stessi fantapunti e non occupa
    weekend suoi.
    """

    criterio: CriterioF1Rush = CriterioF1Rush.PUNTI_PER_POSIZIONE
    giornate_serie_a: int = 6
    punti_per_posizione: tuple[int, ...] = PUNTI_TAPPA_F1

    def __post_init__(self) -> None:
        # Da JSON la scala arriva come lista: una dataclass congelata con una
        # lista dentro non e' piu' confrontabile ne' hashabile come le altre.
        object.__setattr__(self, "punti_per_posizione", tuple(self.punti_per_posizione))
        if self.giornate_serie_a < 1:
            raise CompetizioneNonValida("La F1 Rush dura almeno una giornata")
        if self.criterio is CriterioF1Rush.PUNTI_PER_POSIZIONE and not (
            self.punti_per_posizione
        ):
            raise CompetizioneNonValida(
                "Senza punti per posizione la F1 Rush non assegna niente: "
                "scegli la somma dei fantapunti, o riempi la scala."
            )

    def punti_di_posizione(self, posizione: int) -> int:
        """I punti di chi arriva in quella posizione di tappa (1 = primo).

        Fuori dalla scala si prende zero, come in Formula 1: non si inventa
        un punteggio per chi e' oltre l'ultima posizione premiata.
        """
        if 1 <= posizione <= len(self.punti_per_posizione):
            return self.punti_per_posizione[posizione - 1]
        return 0


@dataclass(frozen=True)
class Titolo:
    """Una riga dell'albo d'oro: chi ha vinto cosa, e quando."""

    id: int
    lega_id: int
    competizione: TipoCompetizione
    stagione: str
    squadra_id: int | None
    squadra_nome: str
    note: str = ""
    registrato_il: str = ""

    def __post_init__(self) -> None:
        nome = (self.squadra_nome or "").strip()
        if not nome:
            raise CompetizioneNonValida("Un titolo senza squadra non ha senso")
        if not str(self.stagione).strip():
            raise CompetizioneNonValida("Un titolo senza stagione non e' storicizzabile")
        object.__setattr__(self, "squadra_nome", nome)

    @property
    def etichetta(self) -> str:
        return f"{self.competizione.icona} {self.competizione.etichetta} {self.stagione}"


def ordina_albo(titoli: list[Titolo]) -> list[Titolo]:
    """Dalla stagione piu' recente, poi campionato, coppa, F1 Rush."""
    ordine = {t: i for i, t in enumerate(TipoCompetizione)}
    return sorted(
        titoli,
        key=lambda t: (t.stagione, -ordine[t.competizione]),
        reverse=True,
    )


def bacheca_squadre(titoli: list[Titolo]) -> dict[str, dict[TipoCompetizione, int]]:
    """Quanti titoli per squadra e per competizione."""
    conteggio: dict[str, dict[TipoCompetizione, int]] = {}
    for titolo in titoli:
        per_squadra = conteggio.setdefault(titolo.squadra_nome, {})
        per_squadra[titolo.competizione] = per_squadra.get(titolo.competizione, 0) + 1
    return conteggio


def titolo_esistente(
    titoli: list[Titolo], competizione: TipoCompetizione, stagione: str
) -> Titolo | None:
    """Una competizione ha un vincitore per stagione: il secondo lo sostituisce."""
    for titolo in titoli:
        if titolo.competizione is competizione and titolo.stagione == stagione:
            return titolo
    return None


@dataclass(frozen=True)
class RigaF1:
    """Una squadra nella classifica della F1 Rush."""

    squadra: str
    punti: int
    fantapunti: float
    tappe: int
    # Quante volte ha vinto la tappa: e' il primo spareggio, come in F1.
    vittorie_di_tappa: int = 0


def classifica_f1(
    tappe: list[dict[str, float]], regole: RegoleF1Rush | None = None
) -> list[RigaF1]:
    """La classifica della F1 Rush da una tappa per giornata.

    Ogni tappa e' `{nome squadra: fantapunti}`: per ogni giornata si ordina
    per fantapunti e si assegnano i punti della scala. A pari fantapunti
    nella stessa tappa valgono i **pari merito**, e tutte prendono i punti
    della posizione migliore — come in una griglia dove nessuno passa avanti
    senza averlo fatto in campo.

    L'ordine finale e' punti, poi vittorie di tappa, poi fantapunti totali:
    sono i due spareggi della Formula 1, nell'ordine in cui li usa lei.
    """
    regole = regole or RegoleF1Rush()
    punti: dict[str, int] = {}
    fantapunti: dict[str, float] = {}
    vittorie: dict[str, int] = {}
    presenze: dict[str, int] = {}

    for tappa in tappe:
        if not tappa:
            continue
        ordinata = sorted(tappa.items(), key=lambda voce: -voce[1])
        # I pari merito prendono tutti i punti della posizione migliore, quindi
        # la posizione si ricava dal punteggio e non dal posto nell'elenco.
        prima_posizione = {}
        for posto, (_, quanti) in enumerate(ordinata, start=1):
            prima_posizione.setdefault(quanti, posto)

        for squadra, suoi in ordinata:
            posizione = prima_posizione[suoi]
            assegnati = (
                regole.punti_di_posizione(posizione)
                if regole.criterio is CriterioF1Rush.PUNTI_PER_POSIZIONE
                else 0
            )
            punti[squadra] = punti.get(squadra, 0) + assegnati
            fantapunti[squadra] = fantapunti.get(squadra, 0.0) + suoi
            presenze[squadra] = presenze.get(squadra, 0) + 1
            if posizione == 1:
                vittorie[squadra] = vittorie.get(squadra, 0) + 1

    righe = [
        RigaF1(
            squadra=squadra,
            punti=punti.get(squadra, 0),
            fantapunti=round(fantapunti.get(squadra, 0.0), 2),
            tappe=presenze.get(squadra, 0),
            vittorie_di_tappa=vittorie.get(squadra, 0),
        )
        for squadra in presenze
    ]
    righe.sort(key=lambda r: (r.punti, r.vittorie_di_tappa, r.fantapunti), reverse=True)
    return righe


def giornate_f1_rush(
    giornate_serie_a: int = GIORNATE_SERIE_A, regole: RegoleF1Rush | None = None
) -> tuple[int, ...]:
    """Su quali turni di Serie A si corre la F1 Rush: gli ultimi sei.

    Con un campionato piu' corto della F1 Rush si prende quel che c'e',
    invece di restituire giornate che non esistono.
    """
    regole = regole or RegoleF1Rush()
    quante = min(regole.giornate_serie_a, max(giornate_serie_a, 0))
    if quante <= 0:
        return ()
    return tuple(range(giornate_serie_a - quante + 1, giornate_serie_a + 1))


def crea_titolo(
    id_: int,
    lega_id: int,
    competizione: TipoCompetizione,
    stagione: str,
    squadra_nome: str,
    squadra_id: int | None = None,
    note: str = "",
) -> Titolo:
    from datetime import datetime, timezone

    return Titolo(
        id=id_,
        lega_id=lega_id,
        competizione=competizione,
        stagione=stagione,
        squadra_id=squadra_id,
        squadra_nome=squadra_nome,
        note=note,
        registrato_il=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def con_vincitrice(titolo: Titolo, squadra_nome: str, squadra_id: int | None) -> Titolo:
    return replace(titolo, squadra_nome=squadra_nome, squadra_id=squadra_id)


# ---------------------------------------------------------------------------
# Il calendario dei weekend
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Weekend:
    """Un turno di Serie A e cosa ci si gioca nella lega.

    Serve a rispondere alla domanda che ci si fa la domenica: «questa
    giornata di Serie A a cosa corrisponde da noi?». Puo' non corrispondere a
    niente (sosta), a una giornata di campionato, o a un turno di coppa.
    """

    giornata_serie_a: int
    impegni: tuple[tuple[TipoCompetizione, str], ...] = ()

    @property
    def libero(self) -> bool:
        return not self.impegni

    @property
    def descrizione(self) -> str:
        if self.libero:
            return "— nessun impegno —"
        return " · ".join(f"{tipo.icona} {etichetta}" for tipo, etichetta in self.impegni)


def costruisci_weekend(
    giornate_serie_a: int,
    giornate_campionato: int,
    regole_coppa: RegoleCoppa | None = None,
    prima_giornata_serie_a: int = 1,
    regole_f1_rush: RegoleF1Rush | None = None,
) -> list[Weekend]:
    """Distribuisce campionato e coppa sui turni di Serie A.

    Il fantacampionato parte da una certa giornata di Serie A (la lega si
    forma dopo il draft di settembre) e da li' avanza di uno per weekend. I
    turni di coppa occupano un weekend intero: in quel fine settimana il
    campionato **non si gioca e non avanza**, quindi slitta di una settimana.
    E' proprio questo slittamento che disallinea le due numerazioni, ed e'
    cio' che la pagina Calendario esiste per mostrare.

    `regole_coppa.giornate_dei_turni()` conta i **weekend della lega**, non le
    giornate di campionato: il primo turno «alla 5ª» significa al quinto
    weekend, che e' il modo in cui la domanda viene posta guardando un
    calendario.

    La **F1 Rush** si comporta diversamente da tutto il resto: non occupa un
    weekend suo e non fa slittare niente, perche' corre sugli stessi
    fantapunti del campionato. Quindi si aggiunge agli impegni di quel
    weekend, accanto alla giornata di lega, e si conta sulle giornate di
    **Serie A** — «le ultime sei» del testo sono quelle, non quelle di lega.
    """

    def turni_di_coppa(regole: RegoleCoppa) -> list[str]:
        """I nomi degli impegni di coppa, in ordine: prima i gironi, poi gli scontri."""
        gironi = [
            f"{n}ª giornata dei gironi" for n in range(1, regole.giornate_di_girone + 1)
        ]
        scontri = [regole.nome_turno(n) for n in range(1, regole.turni + 1)]
        return gironi + scontri

    tappe_f1: dict[int, str] = {}
    if regole_f1_rush is not None:
        turni = giornate_f1_rush(giornate_serie_a, regole_f1_rush)
        for numero, turno in enumerate(turni, start=1):
            tappe_f1[turno] = f"{numero}ª tappa di {len(turni)}"

    turni_coppa: dict[int, str] = {}
    if regole_coppa is not None and not regole_coppa.dopo_il_campionato:
        for numero, weekend_di_coppa in enumerate(
            regole_coppa.giornate_dei_turni(), start=1
        ):
            turni_coppa[weekend_di_coppa] = regole_coppa.nome_turno(numero)
    elif regole_coppa is not None:
        # «Disputati a fine campionato» (art. 1): la coppa non si intervalla,
        # si accoda. Il primo weekend di coppa e' quello dopo l'ultima
        # giornata di lega, e da li' si va di fila.
        for numero, nome in enumerate(turni_di_coppa(regole_coppa), start=1):
            turni_coppa[giornate_campionato + numero] = nome

    weekend: list[Weekend] = []
    giornata_fanta = 1
    for numero_weekend, turno_a in enumerate(
        range(prima_giornata_serie_a, giornate_serie_a + 1), start=1
    ):
        impegni: list[tuple[TipoCompetizione, str]] = []

        if numero_weekend in turni_coppa:
            impegni.append((TipoCompetizione.COPPA_ITALIA, turni_coppa[numero_weekend]))
        elif giornata_fanta <= giornate_campionato:
            impegni.append((TipoCompetizione.CAMPIONATO, f"{giornata_fanta}ª giornata"))
            giornata_fanta += 1

        if turno_a in tappe_f1:
            impegni.append((TipoCompetizione.F1_RUSH, tappe_f1[turno_a]))

        weekend.append(Weekend(giornata_serie_a=turno_a, impegni=tuple(impegni)))
    return weekend


def titoli_di(
    titoli: list[Titolo], squadra_id: int | None, squadra_nome: str
) -> list[Titolo]:
    """I titoli di una squadra, per la sua bacheca.

    Si confronta l'id quando c'e', altrimenti il nome: una squadra che
    cambia nome non deve perdere quello che ha vinto, e un titolo registrato
    prima che l'id fosse noto resta comunque suo.
    """
    nome = (squadra_nome or "").strip().lower()

    def e_suo(titolo: Titolo) -> bool:
        if titolo.squadra_id is not None:
            return titolo.squadra_id == squadra_id
        # Titolo registrato senza id: resta agganciato al nome.
        return titolo.squadra_nome.strip().lower() == nome

    return ordina_albo([t for t in titoli if e_suo(t)])


def conta_per_competizione(titoli: list[Titolo]) -> dict[TipoCompetizione, int]:
    """Quanti titoli per competizione, nell'ordine in cui vanno mostrati."""
    return {
        tipo: sum(1 for t in titoli if t.competizione is tipo)
        for tipo in TipoCompetizione
    }
