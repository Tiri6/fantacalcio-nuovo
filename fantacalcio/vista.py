"""Trasformazioni dai dati grezzi alle tabelle mostrate a schermo.

Modulo puro (solo pandas): non importa Streamlit, cosi' resta testabile e
riutilizzabile da script o notebook.
"""

from __future__ import annotations

import pandas as pd

from .data import Archivio, calendario_dettagliato, prestazioni_dettagliate
from .scoring import Prestazione, RegoleLega, calcola_formazione
from .standings import Partita, calcola_classifica

ETICHETTE_RUOLO = {
    "P": "Portiere",
    "D": "Difensore",
    "C": "Centrocampista",
    "A": "Attaccante",
}


def _opzionale(valore, tipo):
    return None if pd.isna(valore) else tipo(valore)


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
    """Classifica pronta da mostrare, con posizione e colonne in italiano."""
    calendario = calendario_dettagliato(arch)
    righe = calcola_classifica(
        arch.squadre()["nome"].tolist(), partite_dominio(calendario)
    )
    tabella = pd.DataFrame(
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
    if not tabella.empty:
        tabella["Media punti"] = (
            tabella["Punti fantacalcio"] / tabella["PG"].replace(0, pd.NA)
        ).round(2)
    return tabella


def andamento_punti(arch: Archivio) -> pd.DataFrame:
    """Punti fantacalcio per squadra e giornata (per i grafici)."""
    calendario = calendario_dettagliato(arch)
    giocate = calendario[calendario["gol_casa"].notna()]

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


def classifica_marcatori(arch: Archivio, quanti: int = 15) -> pd.DataFrame:
    """Migliori marcatori della lega, con assist e media voto."""
    prestazioni = prestazioni_dettagliate(arch)
    prestazioni["gol_totali"] = prestazioni["gol_segnati"] + prestazioni["gol_su_rigore"]

    aggregato = (
        prestazioni.groupby(["giocatore", "ruolo", "club", "squadra"], dropna=False)
        .agg(
            gol=("gol_totali", "sum"),
            assist=("assist", "sum"),
            presenze=("voto", "count"),
            media_voto=("voto", "mean"),
        )
        .reset_index()
    )
    aggregato["media_voto"] = aggregato["media_voto"].round(2)
    aggregato = aggregato.sort_values(
        ["gol", "assist", "media_voto"], ascending=False
    ).head(quanti)
    return aggregato.reset_index(drop=True)


def migliori_per_media(
    arch: Archivio, presenze_minime: int = 3, quanti: int = 15
) -> pd.DataFrame:
    """Media fantavoto per giocatore, tra chi ha almeno N presenze."""
    prestazioni = prestazioni_dettagliate(arch)
    con_voto = prestazioni[prestazioni["voto"].notna()].copy()
    regole = RegoleLega()

    con_voto["fantavoto"] = [
        calcola_fantavoto_riga(riga, regole) for riga in con_voto.to_dict("records")
    ]
    aggregato = (
        con_voto.groupby(["giocatore", "ruolo", "club", "squadra"], dropna=False)
        .agg(
            presenze=("fantavoto", "count"),
            media_fantavoto=("fantavoto", "mean"),
            media_voto=("voto", "mean"),
        )
        .reset_index()
    )
    aggregato = aggregato[aggregato["presenze"] >= presenze_minime]
    aggregato[["media_fantavoto", "media_voto"]] = aggregato[
        ["media_fantavoto", "media_voto"]
    ].round(2)
    return (
        aggregato.sort_values("media_fantavoto", ascending=False)
        .head(quanti)
        .reset_index(drop=True)
    )


def calcola_fantavoto_riga(riga: dict, regole: RegoleLega | None = None) -> float:
    """Fantavoto di una riga di `prestazioni` (dict o Series convertita in dict)."""
    from .scoring import fantavoto

    regole = regole or RegoleLega()
    return fantavoto(
        Prestazione(
            giocatore_id=int(riga.get("giocatore_id", 0)),
            nome=str(riga.get("giocatore", "")),
            ruolo=str(riga["ruolo"]),
            voto=float(riga["voto"]),
            gol_segnati=int(riga.get("gol_segnati", 0)),
            gol_su_rigore=int(riga.get("gol_su_rigore", 0)),
            rigori_sbagliati=int(riga.get("rigori_sbagliati", 0)),
            rigori_parati=int(riga.get("rigori_parati", 0)),
            gol_subiti=int(riga.get("gol_subiti", 0)),
            autogol=int(riga.get("autogol", 0)),
            assist=int(riga.get("assist", 0)),
            ammonizioni=int(riga.get("ammonizioni", 0)),
            espulsioni=int(riga.get("espulsioni", 0)),
        ),
        regole,
    )


def tabellino_squadra(arch: Archivio, squadra_id: int, giornata: int) -> pd.DataFrame:
    """Formazione schierata da una squadra in una giornata, con i fantavoti.

    Include i panchinari, marcando chi e' entrato per un titolare s.v.
    """
    formazioni = arch.formazioni()
    schierati = formazioni[
        (formazioni["squadra_id"] == squadra_id) & (formazioni["giornata"] == giornata)
    ]
    if schierati.empty:
        return pd.DataFrame()

    prestazioni = prestazioni_dettagliate(arch)
    prestazioni = prestazioni[prestazioni["giornata"] == giornata]
    unione = schierati.merge(prestazioni, on=["giornata", "giocatore_id"], how="left")

    regole = RegoleLega()
    titolari = unione[unione["titolare"] == 1].to_dict("records")
    panchina = (
        unione[unione["titolare"] == 0]
        .sort_values("ordine_panchina")
        .to_dict("records")
    )

    def a_prestazione(riga: dict) -> Prestazione:
        voto = riga.get("voto")
        return Prestazione(
            giocatore_id=int(riga["giocatore_id"]),
            nome=str(riga.get("giocatore") or riga["giocatore_id"]),
            ruolo=str(riga["ruolo"]),
            voto=None if pd.isna(voto) else float(voto),
            gol_segnati=int(riga.get("gol_segnati") or 0),
            gol_su_rigore=int(riga.get("gol_su_rigore") or 0),
            rigori_sbagliati=int(riga.get("rigori_sbagliati") or 0),
            rigori_parati=int(riga.get("rigori_parati") or 0),
            gol_subiti=int(riga.get("gol_subiti") or 0),
            autogol=int(riga.get("autogol") or 0),
            assist=int(riga.get("assist") or 0),
            ammonizioni=int(riga.get("ammonizioni") or 0),
            espulsioni=int(riga.get("espulsioni") or 0),
        )

    risultato = calcola_formazione(
        [a_prestazione(r) for r in titolari],
        [a_prestazione(r) for r in panchina],
        regole,
    )
    entrati = {p.giocatore_id for p in risultato.panchinari_entrati}
    contati = {p.giocatore_id for p in risultato.schierati}

    righe = []
    for riga in titolari + panchina:
        gid = int(riga["giocatore_id"])
        titolare = riga["titolare"] == 1
        if titolare:
            stato = "Titolare" if gid in contati else "s.v."
        else:
            stato = "Entrato" if gid in entrati else "Panchina"
        righe.append(
            {
                "Giocatore": riga.get("giocatore"),
                "Ruolo": ETICHETTE_RUOLO.get(riga["ruolo"], riga["ruolo"]),
                "Club": riga.get("club"),
                "Voto": riga.get("voto"),
                "Fantavoto": risultato.dettaglio.get(gid),
                "Stato": stato,
            }
        )

    tabellino = pd.DataFrame(righe)
    # Voto e fantavoto diventano testo: st.dataframe stampa "None" nelle celle
    # nulle di una colonna numerica, e in un tabellino si legge male. Qui non
    # serve ordinare per voto, quindi il trattino e' il compromesso giusto.
    for colonna in ("Voto", "Fantavoto"):
        tabellino[colonna] = [
            "—" if v is None or pd.isna(v) else f"{float(v):.1f}"
            for v in tabellino[colonna]
        ]

    tabellino.attrs["totale"] = risultato.totale
    tabellino.attrs["gol"] = risultato.gol
    return tabellino
