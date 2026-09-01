"""Parametri del regolamento di FantaCalcio NuoVo (V2.1 - Agosto 2026).

Ogni numero del regolamento sta qui e da nessun'altra parte: le regole della
lega cambiano per votazione ("lodi"), quindi devono essere modificabili in un
punto solo senza toccare la logica.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

# --- Ruoli Mantra -----------------------------------------------------------
# La lega gioca in modalita' Mantra: un giocatore puo' avere piu' ruoli.
RUOLI_MANTRA = ("Por", "Dc", "Dd", "Ds", "B", "E", "M", "C", "W", "T", "A", "Pc")

ETICHETTE_RUOLO = {
    "Por": "Portiere",
    "Dc": "Difensore centrale",
    "Dd": "Terzino destro",
    "Ds": "Terzino sinistro",
    "B": "Braccetto",
    "E": "Esterno",
    "M": "Mediano",
    "C": "Centrocampista centrale",
    "W": "Ala",
    "T": "Trequartista",
    "A": "Attaccante",
    "Pc": "Punta centrale",
}

RUOLO_PORTIERE = "Por"


@dataclass(frozen=True)
class SogliaAnnuali:
    """Regola "1/3": quanti contratti annuali servono per una data dimensione rosa."""

    rosa_da: int
    rosa_a: int
    minimo_annuali: int


@dataclass(frozen=True)
class ParametriLega:
    """Tutti i vincoli numerici del regolamento.

    I default sono quelli della V2.1. Un lodo che cambia un valore si applica
    costruendo un nuovo ParametriLega, senza toccare il codice delle regole.
    """

    stagione: str = "2026/27"
    partecipanti: int = 10

    # Articolo 2 - Composizione rosa
    rosa_minimo: int = 30
    rosa_massimo_base: int = 33
    rosa_massimo_assoluto: int = 36
    portieri_massimo: int = 3

    # Articolo 2 - Espansione Under 21 (sponsor italiannextgen.it)
    slot_u21_massimi: int = 3
    eta_limite_u21: int = 21
    nazionalita_u21: str = "Italia"

    # Articolo 2 - Monte anni e durata contratti
    monte_anni: int = 66
    contratto_anni_minimo: int = 1
    contratto_anni_massimo: int = 5

    # Articolo 2 - Regola "1/3": quota di rosa in scadenza
    soglie_annuali: tuple[SogliaAnnuali, ...] = (
        SogliaAnnuali(30, 30, 10),
        SogliaAnnuali(31, 33, 11),
        SogliaAnnuali(34, 36, 12),
    )

    # Articolo 4 - Economia (fonte stipendi: Capology)
    salary_cap: float = 100_000_000.0
    salary_floor: float = 80_000_000.0
    salary_floor_attivo: bool = True

    # Articolo 7 - Svincoli (Lodo Origi)
    quota_dead_money: float = 0.50

    # Articolo 8 - Scambi (Lodo Longoni emendato, Lodo Corti)
    prolungamenti_per_squadra_a_stagione: int = 2
    prolungamenti_per_giocatore_in_lega: int = 1
    ore_ratifica_scambio: int = 24

    # Articolo 5 - Finestre di mercato: gironcini da 9 giornate
    giornate_per_gironcino: int = 9

    # Articolo 1 - Fasce di gol (di 6 in 6). Vedi NOTA in fondo al modulo.
    soglia_primo_gol: float = 66.0
    passo_gol: float = 6.0
    modificatore_difesa: bool = True

    # Mantra: chi gioca in un posto che non e' suo prende un malus. E' la
    # regola della piattaforma (un punto pieno), e vale sia per chi parte
    # titolare fuori posizione sia per chi entra adattato dalla panchina.
    malus_adattamento: float = 1.0

    def rosa_massimo(self, slot_u21: int = 0) -> int:
        """Limite massimo di rosa, ampliato di un posto per ogni U21 tesserato."""
        slot = max(0, min(slot_u21, self.slot_u21_massimi))
        return min(self.rosa_massimo_base + slot, self.rosa_massimo_assoluto)

    def minimo_annuali(self, dimensione_rosa: int) -> int:
        """Contratti da 1 anno richiesti per una rosa di quella dimensione."""
        for soglia in self.soglie_annuali:
            if soglia.rosa_da <= dimensione_rosa <= soglia.rosa_a:
                return soglia.minimo_annuali
        # Fuori dalle fasce previste: si applica la fascia piu' vicina.
        if dimensione_rosa < self.soglie_annuali[0].rosa_da:
            return self.soglie_annuali[0].minimo_annuali
        return self.soglie_annuali[-1].minimo_annuali


@dataclass(frozen=True)
class CalendarioStagione:
    """Date che governano mercato e status U21."""

    data_draft_settembre: date
    giornate_totali: int = 27
    # Articolo 5: la finestra invernale apre dopo la 9a, la primaverile dopo la 18a.
    giornate_apertura_finestre: tuple[int, ...] = (9, 18)
    lodi: tuple[str, ...] = field(default_factory=tuple)


def fasce_gol(punti: float, parametri: ParametriLega) -> int:
    """Converte i punti di squadra in gol secondo le fasce della lega."""
    if punti < parametri.soglia_primo_gol:
        return 0
    return 1 + int((punti - parametri.soglia_primo_gol) // parametri.passo_gol)


def parametri_da_dict(valori: dict) -> ParametriLega:
    """Costruisce i parametri da un dict (es. tabella `parametri` su Supabase)."""
    campi = set(ParametriLega.__dataclass_fields__)
    return replace(ParametriLega(), **{k: v for k, v in valori.items() if k in campi})


# NOTA APERTA (da votare, vedi PUNTI_APERTI.md)
# Il regolamento elenca le fasce come "60-66-72-78-84-90". Se 60 fosse il primo
# gol, la sequenza dei successivi cadrebbe su 66, 72, 78: coincide con lo
# standard di Leghe Fantacalcio, dove pero' il primo gol scatta a 66. Qui il
# default e' 66 (comportamento della piattaforma su cui giocate davvero);
# se la lega intende 60, basta cambiare `soglia_primo_gol`.
