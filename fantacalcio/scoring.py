"""Calcolo del fantavoto e conversione punti -> gol.

Le regole sono quelle "classiche" della Lega Fantacalcio: ogni bonus/malus e'
configurabile tramite `RegoleLega` perche' ogni lega applica varianti proprie.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace

# Ruoli classici (Mantra non e' supportato in questa prima versione).
RUOLI = ("P", "D", "C", "A")


@dataclass(frozen=True)
class RegoleLega:
    """Bonus/malus e parametri di conversione della lega."""

    gol_segnato: float = 3.0
    gol_su_rigore: float = 3.0
    rigore_sbagliato: float = -3.0
    rigore_parato: float = 3.0
    gol_subito: float = -1.0
    autogol: float = -2.0
    assist: float = 1.0
    ammonizione: float = -0.5
    espulsione: float = -1.0
    porta_inviolata: float = 0.0

    # Soglia del primo gol e passo per i gol successivi.
    soglia_primo_gol: float = 66.0
    passo_gol: float = 6.0

    # Numero di titolari schierati e panchinari utilizzabili come sostituti.
    titolari: int = 11
    max_sostituzioni: int = 3

    # Modificatore difesa: disattivato di default.
    modificatore_difesa: bool = False


@dataclass(frozen=True)
class Prestazione:
    """Prestazione di un singolo giocatore in una giornata.

    `voto` a None significa "senza voto" (s.v.): il giocatore non entra nel
    calcolo e va sostituito con un panchinaro.
    """

    giocatore_id: int
    nome: str
    ruolo: str
    voto: float | None = None
    gol_segnati: int = 0
    gol_su_rigore: int = 0
    rigori_sbagliati: int = 0
    rigori_parati: int = 0
    gol_subiti: int = 0
    autogol: int = 0
    assist: int = 0
    ammonizioni: int = 0
    espulsioni: int = 0

    @property
    def senza_voto(self) -> bool:
        return self.voto is None


@dataclass(frozen=True)
class RisultatoFormazione:
    """Esito del calcolo di una formazione per una giornata."""

    totale: float
    gol: int
    schierati: tuple[Prestazione, ...]
    panchinari_entrati: tuple[Prestazione, ...]
    non_sostituiti: tuple[Prestazione, ...]
    modificatore: float = 0.0
    dettaglio: dict[int, float] = field(default_factory=dict)


def fantavoto(prestazione: Prestazione, regole: RegoleLega) -> float:
    """Voto in pagella + bonus/malus. Solleva ValueError se il giocatore e' s.v."""
    if prestazione.senza_voto:
        raise ValueError(
            f"{prestazione.nome} e' senza voto: non ha un fantavoto calcolabile"
        )

    totale = float(prestazione.voto)
    totale += prestazione.gol_segnati * regole.gol_segnato
    totale += prestazione.gol_su_rigore * regole.gol_su_rigore
    totale += prestazione.rigori_sbagliati * regole.rigore_sbagliato
    totale += prestazione.rigori_parati * regole.rigore_parato
    totale += prestazione.gol_subiti * regole.gol_subito
    totale += prestazione.autogol * regole.autogol
    totale += prestazione.assist * regole.assist
    totale += prestazione.ammonizioni * regole.ammonizione
    totale += prestazione.espulsioni * regole.espulsione

    if (
        regole.porta_inviolata
        and prestazione.ruolo == "P"
        and prestazione.gol_subiti == 0
    ):
        totale += regole.porta_inviolata

    return round(totale, 2)


def punti_in_gol(punti: float, regole: RegoleLega) -> int:
    """Converte il punteggio della formazione in gol segnati.

    Sotto la soglia sono 0 gol; alla soglia e' 1 gol; poi un gol ogni `passo_gol`.
    Con i default (66 / 6): 65.5 -> 0, 66 -> 1, 72 -> 2, 78 -> 3.
    """
    if punti < regole.soglia_primo_gol:
        return 0
    extra = punti - regole.soglia_primo_gol
    return 1 + int(extra // regole.passo_gol)


def _sostituto_valido(
    panchina: Iterable[Prestazione], usati: set[int], ruolo: str
) -> Prestazione | None:
    """Primo panchinaro con voto e stesso ruolo, seguendo l'ordine di panchina."""
    for candidato in panchina:
        if candidato.giocatore_id in usati:
            continue
        if candidato.senza_voto:
            continue
        if candidato.ruolo != ruolo:
            continue
        return candidato
    return None


def _modificatore_difesa(schierati: Sequence[Prestazione], regole: RegoleLega) -> float:
    """Bonus in base alla media di portiere + 3 migliori difensori.

    Si applica solo se la formazione schiera almeno 4 difensori, come da
    regolamento classico.
    """
    portieri = [p for p in schierati if p.ruolo == "P"]
    difensori = sorted(
        (p for p in schierati if p.ruolo == "D"),
        key=lambda p: fantavoto(p, regole),
        reverse=True,
    )
    if not portieri or len(difensori) < 4:
        return 0.0

    voti = [float(portieri[0].voto)] + [float(d.voto) for d in difensori[:3]]
    media = sum(voti) / len(voti)

    soglie = [
        (6.5, 1.0),
        (7.0, 2.0),
        (7.5, 3.0),
        (8.0, 4.0),
        (8.5, 5.0),
        (9.0, 6.0),
    ]
    bonus = 0.0
    for soglia, valore in soglie:
        if media >= soglia:
            bonus = valore
    return bonus


def calcola_formazione(
    titolari: Sequence[Prestazione],
    panchina: Sequence[Prestazione] = (),
    regole: RegoleLega | None = None,
) -> RisultatoFormazione:
    """Applica le sostituzioni, somma i fantavoti e converte il totale in gol."""
    regole = regole or RegoleLega()

    if len(titolari) != regole.titolari:
        raise ValueError(
            f"Servono {regole.titolari} titolari, ne sono stati passati {len(titolari)}"
        )

    usati: set[int] = set()
    schierati: list[Prestazione] = []
    entrati: list[Prestazione] = []
    non_sostituiti: list[Prestazione] = []

    for titolare in titolari:
        if not titolare.senza_voto:
            schierati.append(titolare)
            continue

        if len(entrati) >= regole.max_sostituzioni:
            non_sostituiti.append(titolare)
            continue

        sostituto = _sostituto_valido(panchina, usati, titolare.ruolo)
        if sostituto is None:
            non_sostituiti.append(titolare)
            continue

        usati.add(sostituto.giocatore_id)
        schierati.append(sostituto)
        entrati.append(sostituto)

    dettaglio = {p.giocatore_id: fantavoto(p, regole) for p in schierati}
    totale = round(sum(dettaglio.values()), 2)

    modificatore = (
        _modificatore_difesa(schierati, regole) if regole.modificatore_difesa else 0.0
    )
    totale = round(totale + modificatore, 2)

    return RisultatoFormazione(
        totale=totale,
        gol=punti_in_gol(totale, regole),
        schierati=tuple(schierati),
        panchinari_entrati=tuple(entrati),
        non_sostituiti=tuple(non_sostituiti),
        modificatore=modificatore,
        dettaglio=dettaglio,
    )


def regole_da_dict(valori: dict) -> RegoleLega:
    """Costruisce le regole partendo da un dict (es. tabella `regole` su Supabase).

    Le chiavi sconosciute vengono ignorate, cosi' il DB puo' evolvere senza
    rompere l'app.
    """
    campi = set(RegoleLega.__dataclass_fields__)
    puliti = {k: v for k, v in valori.items() if k in campi}
    return replace(RegoleLega(), **puliti)
