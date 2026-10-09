"""Dai dati grezzi alle tabelle mostrate a schermo.

Modulo puro (solo pandas): non importa Streamlit, cosi' resta testabile e
riutilizzabile se un domani il sito cambia tecnologia.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from .competizioni import RegoleF1Rush, classifica_f1, giornate_f1_rush
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


def tappe_f1(arch: Archivio, regole: RegoleF1Rush | None = None) -> list[dict]:
    """Le tappe della F1 Rush: una riga per giornata, coi fantapunti di tutti.

    Le tappe sono «le ultime sei giornate di Serie A» (art. 1). Il calendario
    porta `giornata_serie_a` quando chi ha importato i risultati l'ha
    compilata: in quel caso si filtra su quella, che e' la lettura letterale
    del testo. Quando manca si prendono le **ultime giornate di lega**
    disputate, che e' l'approssimazione piu' vicina — e si preferisce quella a
    non mostrare niente.

    Ogni voce e' `{"giornata": n, "serie_a": m | None, "punti": {squadra: p}}`:
    la classifica la fa `competizioni.classifica_f1`, che non sa niente di
    DataFrame.
    """
    regole = regole or RegoleF1Rush()
    calendario = calendario_dettagliato(arch)
    if calendario.empty:
        return []
    giocate = calendario[calendario["punti_casa"].notna()]
    if giocate.empty:
        return []

    turni = giornate_f1_rush(regole=regole)
    ha_serie_a = (
        "giornata_serie_a" in giocate.columns
        and giocate["giornata_serie_a"].notna().any()
    )
    if ha_serie_a:
        scelte = giocate[giocate["giornata_serie_a"].isin(turni)]
    else:
        ultime = sorted(giocate["giornata"].unique())[-regole.giornate_serie_a :]
        scelte = giocate[giocate["giornata"].isin(ultime)]
    if scelte.empty:
        return []

    tappe: list[dict] = []
    for giornata in sorted(scelte["giornata"].unique()):
        righe = scelte[scelte["giornata"] == giornata]
        punti: dict[str, float] = {}
        serie_a = None
        for r in righe.itertuples():
            punti[r.casa] = float(r.punti_casa)
            punti[r.trasferta] = float(r.punti_trasferta)
            if ha_serie_a and not pd.isna(r.giornata_serie_a):
                serie_a = int(r.giornata_serie_a)
        tappe.append({"giornata": int(giornata), "serie_a": serie_a, "punti": punti})
    return tappe


def classifica_f1_tabella(
    arch: Archivio, regole: RegoleF1Rush | None = None
) -> pd.DataFrame:
    """La classifica della F1 Rush, pronta da mostrare."""
    regole = regole or RegoleF1Rush()
    righe = classifica_f1([t["punti"] for t in tappe_f1(arch, regole)], regole)
    if not righe:
        return pd.DataFrame(
            columns=["Pos", "Squadra", "Punti", "Vittorie di tappa", "Fantapunti"]
        )
    return pd.DataFrame(
        [
            {
                "Pos": posizione,
                "Squadra": r.squadra,
                "Punti": r.punti,
                "Vittorie di tappa": r.vittorie_di_tappa,
                "Fantapunti": r.fantapunti,
            }
            for posizione, r in enumerate(righe, start=1)
        ]
    )


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
                "Anni": f"{stato.anni_impegnati}/{stato.monte_anni}",
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


# Come si chiama, nelle tabelle, un giocatore che non ha contratto.
SVINCOLATO = "— svincolato —"


def elenco_giocatori(
    arch: Archivio,
    riferimento: date,
    parametri: ParametriLega | None = None,
    nomi_squadre: dict[int, str] | None = None,
) -> list[dict]:
    """Il listone con chi possiede ciascuno, e i flag Ita / U21.

    Sta qui e non nella pagina perche' lo chiedono in due — Streamlit e
    l'API — e una seconda copia diverge alla prima colonna aggiunta: una
    delle due la prenderebbe e l'altra no, senza che niente lo segnali.

    Restituisce dizionari e non un DataFrame: a chi serve una tabella la
    costruisce in una riga, mentre il contrario costringerebbe l'API a
    smontare un DataFrame per rifarne del JSON.
    """
    from .data import carica_giocatori

    parametri = parametri or ParametriLega()
    giocatori = carica_giocatori(arch)
    if not giocatori:
        return []

    nomi = nomi_squadre or {}
    contratti = arch.contratti()
    proprietario: dict[int, tuple[str, int]] = {}
    if not contratti.empty:
        for _, c in contratti.iterrows():
            proprietario[int(c["giocatore_id"])] = (
                nomi.get(int(c["squadra_id"]), "?"),
                int(c["anni_residui"]),
            )

    righe = []
    for giocatore in giocatori.values():
        squadra, anni = proprietario.get(giocatore.id, (SVINCOLATO, 0))
        righe.append(
            {
                "id": giocatore.id,
                "nome": giocatore.nome,
                "club": giocatore.club,
                "ruoli": list(giocatore.ruoli),
                "ruolo_classic": giocatore.ruolo_classic,
                "squadra": squadra,
                "anni": anni,
                "ingaggio": giocatore.ingaggio,
                "nazionalita": giocatore.nazionalita,
                "data_nascita": (
                    giocatore.data_nascita.isoformat() if giocatore.data_nascita else None
                ),
                "eta": giocatore.eta_al(riferimento),
                "italiano": giocatore.italiano,
                "u21": giocatore.under_21(riferimento, parametri),
                "quotazione": giocatore.quotazione,
                "fvm": giocatore.fvm,
            }
        )

    righe.sort(key=lambda r: r["nome"])
    return righe


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
