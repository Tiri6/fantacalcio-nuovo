"""Dai dati grezzi alle tabelle mostrate a schermo.

Modulo puro (solo pandas): non importa Streamlit, cosi' resta testabile e
riutilizzabile se un domani il sito cambia tecnologia.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from .conformita import Momento, StatoRosa, verifica_rosa
from .data import Archivio, calendario_dettagliato
from .modelli import Rosa
from .regole import ETICHETTE_RUOLO, ParametriLega
from .standings import Partita, calcola_classifica


def _opzionale(valore, tipo):
    return None if pd.isna(valore) else tipo(valore)


def milioni(importo: float) -> str:
    return f"{importo / 1_000_000:.2f}M"


def partite_dominio(calendario: pd.DataFrame) -> list[Partita]:
    """Converte il calendario (DataFrame) negli oggetti usati dalla classifica."""
    return [
        Partita(
            giornata=int(r.giornata),
            casa=r.casa,
            trasferta=r.trasferta,
            gol_casa=_opzionale(r.gol_casa, int),
            gol_trasferta=_opzionale(r.gol_trasferta, int),
            punti_casa=_opzionale(r.punti_casa, float),
            punti_trasferta=_opzionale(r.punti_trasferta, float),
        )
        for r in calendario.itertuples()
    ]


def classifica(arch: Archivio) -> pd.DataFrame:
    """Classifica del campionato: e' anche l'input della Draft Lottery."""
    calendario = calendario_dettagliato(arch)
    righe = calcola_classifica(
        arch.squadre()["nome"].tolist(), partite_dominio(calendario)
    )
    return pd.DataFrame(
        [
            {
                "Pos": posizione,
                "Squadra": r.squadra,
                "PG": r.giocate,
                "V": r.vinte,
                "N": r.pareggiate,
                "P": r.perse,
                "GF": r.gol_fatti,
                "GS": r.gol_subiti,
                "DR": r.differenza_reti,
                "Punti": r.punti,
                "Punti fantacalcio": r.punti_fantacalcio,
            }
            for posizione, r in enumerate(righe, start=1)
        ]
    )


def andamento_punti(arch: Archivio) -> pd.DataFrame:
    """Punti fantacalcio per squadra e giornata (per i grafici)."""
    calendario = calendario_dettagliato(arch)
    giocate = calendario[calendario["gol_casa"].notna()]
    if giocate.empty:
        return pd.DataFrame(columns=["giornata", "squadra", "punti", "gol"])

    casa = giocate[["giornata", "casa", "punti_casa", "gol_casa"]].rename(
        columns={"casa": "squadra", "punti_casa": "punti", "gol_casa": "gol"}
    )
    colonne_fuori = ["giornata", "trasferta", "punti_trasferta", "gol_trasferta"]
    fuori = giocate[colonne_fuori].rename(
        columns={
            "trasferta": "squadra",
            "punti_trasferta": "punti",
            "gol_trasferta": "gol",
        }
    )
    unione = pd.concat([casa, fuori], ignore_index=True)
    return unione.sort_values(["squadra", "giornata"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Il cuore del gestionale: conformita' delle rose
# ---------------------------------------------------------------------------


def stati_rose(
    rose: dict[int, Rosa],
    data_draft: date,
    parametri: ParametriLega | None = None,
    momento: Momento = Momento.STAGIONE,
) -> dict[int, StatoRosa]:
    """Verifica tutte le rose della lega."""
    return {
        squadra_id: verifica_rosa(rosa, data_draft, parametri, momento)
        for squadra_id, rosa in rose.items()
    }


def cruscotto_lega(stati: dict[int, StatoRosa]) -> pd.DataFrame:
    """Una riga per squadra con tutti i vincoli del regolamento a colpo d'occhio."""
    righe = []
    for stato in stati.values():
        righe.append(
            {
                "Squadra": stato.squadra,
                "Rosa": f"{stato.dimensione}/{stato.limite_dimensione}",
                "U21": stato.slot_u21,
                "Portieri": stato.portieri,
                "Anni": f"{stato.anni_impegnati}/66",
                "Anni liberi": stato.anni_disponibili,
                "Annuali": f"{stato.contratti_annuali}/{stato.annuali_richiesti}",
                "Ingaggi": stato.monte_ingaggi,
                "Dead money": stato.dead_money,
                "Spesa": stato.spesa_salariale,
                "Spazio cap": stato.spazio_salariale,
                "Esito": "Conforme" if stato.conforme else "Da sistemare",
                "Violazioni": len(stato.violazioni),
            }
        )
    tabella = pd.DataFrame(righe)
    if tabella.empty:
        return tabella
    return tabella.sort_values(["Esito", "Squadra"]).reset_index(drop=True)


def violazioni_lega(stati: dict[int, StatoRosa]) -> pd.DataFrame:
    """Elenco piatto di tutte le violazioni aperte, per l'area del presidente."""
    righe = [
        {
            "Squadra": stato.squadra,
            "Articolo": v.articolo,
            "Gravita": v.gravita.value.capitalize(),
            "Regola": v.codice,
            "Problema": v.messaggio,
        }
        for stato in stati.values()
        for v in stato.violazioni
    ]
    return pd.DataFrame(
        righe, columns=["Squadra", "Articolo", "Gravita", "Regola", "Problema"]
    )


def rosa_dettagliata(
    rosa: Rosa, data_draft: date, parametri: ParametriLega | None = None
) -> pd.DataFrame:
    """La rosa di una squadra con contratti, ingaggi e status Under 21."""
    parametri = parametri or ParametriLega()
    righe = []
    for contratto in rosa.contratti:
        giocatore = rosa.giocatore(contratto.giocatore_id)
        righe.append(
            {
                "Giocatore": giocatore.nome,
                "Ruoli": " / ".join(ETICHETTE_RUOLO.get(r, r) for r in giocatore.ruoli),
                "Club": giocatore.club,
                "Eta": giocatore.eta_al(data_draft),
                "U21": "Si" if giocatore.under_21(data_draft, parametri) else "",
                "Anni residui": contratto.anni_residui,
                "In scadenza": "Si" if contratto.in_scadenza else "",
                "Prolungato": "Si" if contratto.prolungato else "",
                "Ingaggio": giocatore.ingaggio,
                "Valore residuo": contratto.valore_residuo(giocatore.ingaggio),
                "Dead money se tagliato": round(
                    parametri.quota_dead_money
                    * contratto.valore_residuo(giocatore.ingaggio),
                    2,
                ),
            }
        )

    tabella = pd.DataFrame(righe)
    if tabella.empty:
        return tabella
    return tabella.sort_values(
        ["Anni residui", "Ingaggio"], ascending=[True, False]
    ).reset_index(drop=True)


def contratti_in_scadenza(rose: dict[int, Rosa], data_draft: date) -> pd.DataFrame:
    """Chi va a scadenza a fine stagione: la draft list della prossima asta."""
    righe = []
    for rosa in rose.values():
        for contratto in rosa.contratti_annuali:
            giocatore = rosa.giocatore(contratto.giocatore_id)
            righe.append(
                {
                    "Squadra": rosa.squadra.nome,
                    "Giocatore": giocatore.nome,
                    "Club": giocatore.club,
                    "Ruoli": " / ".join(giocatore.ruoli),
                    "Eta": giocatore.eta_al(data_draft),
                    "Ingaggio": giocatore.ingaggio,
                }
            )
    tabella = pd.DataFrame(
        righe, columns=["Squadra", "Giocatore", "Club", "Ruoli", "Eta", "Ingaggio"]
    )
    if tabella.empty:
        return tabella
    return tabella.sort_values(["Squadra", "Ingaggio"], ascending=[True, False])
