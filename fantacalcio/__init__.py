"""FantaCalcio NuoVo: il gestionale della lega.

Il gioco (voti, formazioni, risultati) si svolge su Leghe Fantacalcio. Questo
progetto governa quello che la piattaforma non sa fare: contratti pluriennali,
monte anni, Salary Cap e Floor, draft con lottery, scambi e svincoli secondo il
regolamento della lega.
"""

from .conformita import Gravita, Momento, StatoRosa, Violazione, verifica_rosa
from .draft import (
    EsitoLottery,
    distribuzione_pick,
    ordine_riparazione,
    ordine_round,
    sorteggia_lottery,
    tabellone_draft,
)
from .mercato import (
    Finestra,
    PropostaScambio,
    applica_scambio,
    calcola_dead_money,
    scambio_ratificabile,
    stato_mercato,
    svincola,
    valida_scambio,
)
from .modelli import Contratto, Giocatore, Rosa, Squadra, VoceDeadMoney
from .regole import (
    ETICHETTE_RUOLO,
    RUOLI_MANTRA,
    CalendarioStagione,
    ParametriLega,
    fasce_gol,
    parametri_da_dict,
)
from .standings import (
    Calendario,
    Partita,
    RigaClassifica,
    calcola_classifica,
    genera_calendario,
)

__all__ = [
    "ETICHETTE_RUOLO",
    "RUOLI_MANTRA",
    "Calendario",
    "CalendarioStagione",
    "Contratto",
    "EsitoLottery",
    "Finestra",
    "Giocatore",
    "Gravita",
    "Momento",
    "ParametriLega",
    "Partita",
    "PropostaScambio",
    "RigaClassifica",
    "Rosa",
    "Squadra",
    "StatoRosa",
    "Violazione",
    "VoceDeadMoney",
    "applica_scambio",
    "calcola_classifica",
    "calcola_dead_money",
    "distribuzione_pick",
    "fasce_gol",
    "genera_calendario",
    "ordine_riparazione",
    "ordine_round",
    "parametri_da_dict",
    "scambio_ratificabile",
    "sorteggia_lottery",
    "stato_mercato",
    "svincola",
    "tabellone_draft",
    "valida_scambio",
    "verifica_rosa",
]
