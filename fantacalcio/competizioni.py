"""Le competizioni della lega: campionato, Coppa Italia, Supercoppa, albo d'oro.

Una lega non e' solo il campionato. Qui stanno le regole di chi si affronta e
quando, e il registro di chi ha vinto cosa.

Il campionato c'e' sempre; coppa e supercoppa si accendono creando la lega.
Non e' una preferenza estetica: una lega senza coppa non deve vedere pagine
che parlano di una competizione che non gioca.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import Enum

# Articolo 2, V2.1: «si considera Under 21 il calciatore di nazionalita'
# italiana che non abbia compiuto 21 anni **alla data del draft di Settembre**;
# lo status cosi' determinato resta valido per l'intera stagione».
#
# La data e' quella del draft, non una data fissa di calendario: spostare il
# draft sposta anche chi e' Under. Quando il draft non e' ancora fissato serve
# comunque una data per mostrare qualcosa, e si usa il 31 agosto — l'ultimo
# giorno prima del mese del draft.
GIORNO_RIFERIMENTO_SENZA_DRAFT = (8, 31)


def data_riferimento_u21(stagione: str, data_draft: date | None = None) -> date:
    """La data a cui si guarda l'eta' per decidere chi e' Under 21.

    E' la data del draft di Settembre (articolo 2). `data_draft` a None vuol
    dire che il draft non e' ancora fissato: si ripiega sul 31 agosto della
    stagione, ricavato da '2026/27'. Una stagione scritta male non deve far
    fallire il caricamento di una rosa: li' si usa l'anno corrente, che e'
    l'ipotesi meno sbagliata.
    """
    if data_draft is not None:
        return data_draft
    mese, giorno = GIORNO_RIFERIMENTO_SENZA_DRAFT
    try:
        anno = int(str(stagione).split("/")[0])
    except (ValueError, AttributeError, IndexError):
        anno = date.today().year
    return date(anno, mese, giorno)


class TipoCompetizione(Enum):
    CAMPIONATO = "Campionato"
    COPPA_ITALIA = "Coppa Italia"
    SUPERCOPPA = "Supercoppa"

    @property
    def etichetta(self) -> str:
        return self.value

    @property
    def icona(self) -> str:
        return {"Campionato": "🏆", "Coppa Italia": "🥇", "Supercoppa": "🏅"}[self.value]


class FormatoCoppa(Enum):
    ELIMINAZIONE_SECCA = "Eliminazione diretta, gara secca"
    ANDATA_RITORNO = "Eliminazione diretta, andata e ritorno"
    GIRONI_PIU_SCONTRI = "Gironi, poi eliminazione diretta"

    @property
    def etichetta(self) -> str:
        return self.value


class CriterioSupercoppa(Enum):
    """Chi si affronta in Supercoppa."""

    CAMPIONE_E_COPPA = "Vincitrice campionato contro vincitrice Coppa Italia"
    CAMPIONE_E_SECONDA = "Vincitrice campionato contro seconda classificata"
    MANUALE = "Le scelgo io"

    @property
    def etichetta(self) -> str:
        return self.value


class CompetizioneNonValida(ValueError):
    pass


@dataclass(frozen=True)
class RegoleCoppa:
    """Come si gioca la Coppa Italia.

    I default seguono la coppa di Leghe Fantacalcio: eliminazione diretta a
    gara secca, teste di serie dalla classifica, e in caso di parita' passa
    chi ha fatto piu' fantapunti.
    """

    formato: FormatoCoppa = FormatoCoppa.ELIMINAZIONE_SECCA
    squadre_ammesse: int = 8
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
        if self.squadre_ammesse & (self.squadre_ammesse - 1):
            raise CompetizioneNonValida(
                f"Le squadre ammesse devono essere una potenza di due "
                f"(2, 4, 8, 16): hai scelto {self.squadre_ammesse}"
            )
        if self.prima_giornata < 1:
            raise CompetizioneNonValida("La prima giornata di coppa parte da 1")
        if self.ogni_quante_giornate < 1:
            raise CompetizioneNonValida(
                "Fra un turno di coppa e l'altro serve almeno una giornata"
            )

    @property
    def turni(self) -> int:
        """Quanti turni servono per arrivare alla finale."""
        turni, squadre = 0, self.squadre_ammesse
        while squadre > 1:
            squadre //= 2
            turni += 1
        return turni

    def nome_turno(self, numero: int) -> str:
        """«Ottavi», «Quarti», «Semifinale», «Finale» a seconda di quante restano."""
        rimaste = self.squadre_ammesse // (2 ** (numero - 1))
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


@dataclass(frozen=True)
class RegoleSupercoppa:
    criterio: CriterioSupercoppa = CriterioSupercoppa.CAMPIONE_E_COPPA
    # Gara secca, prima dell'inizio del campionato: e' la norma.
    prima_della_stagione: bool = True


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
    """Dalla stagione piu' recente, poi campionato, coppa, supercoppa."""
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


def finaliste_supercoppa(
    titoli: list[Titolo], regole: RegoleSupercoppa, stagione_precedente: str
) -> tuple[str | None, str | None]:
    """Chi gioca la Supercoppa, dedotto dall'albo d'oro.

    Il primo anno l'albo e' vuoto e non si deduce niente: le due squadre le
    sceglie l'amministratore a mano. Dall'anno dopo si ricavano da sole.
    """
    if regole.criterio is CriterioSupercoppa.MANUALE:
        return (None, None)

    campione = titolo_esistente(titoli, TipoCompetizione.CAMPIONATO, stagione_precedente)
    if regole.criterio is CriterioSupercoppa.CAMPIONE_E_COPPA:
        sfidante = titolo_esistente(
            titoli, TipoCompetizione.COPPA_ITALIA, stagione_precedente
        )
    else:
        sfidante = None

    return (
        campione.squadra_nome if campione else None,
        sfidante.squadra_nome if sfidante else None,
    )


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
    """
    turni_coppa: dict[int, str] = {}
    if regole_coppa is not None:
        for numero, weekend_di_coppa in enumerate(
            regole_coppa.giornate_dei_turni(), start=1
        ):
            turni_coppa[weekend_di_coppa] = regole_coppa.nome_turno(numero)

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
