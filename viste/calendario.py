"""Calendario: tutti gli scontri diretti fra le squadre della lega.

Tre modi di guardare le stesse partite, perche' le domande sono tre:
«cosa si gioca questa giornata», «come e' finita fra me e lui», «che stagione
ho davanti». I risultati arrivano da Leghe Fantacalcio via importazione.
"""

from contextlib import nullcontext

import pandas as pd
import streamlit as st

from fantacalcio import tema, ui
from fantacalcio.competizioni import costruisci_weekend

ui.intestazione(
    "Calendario",
    "📅",
    "Tutti gli incroci della stagione: per giornata, faccia a faccia, o "
    "squadra per squadra.",
)
ui.barra_laterale()

lega = ui.lega_corrente()
opzioni = lega.opzioni

partite = ui.calendario()
# La vista weekend non ha bisogno delle partite: si costruisce dalle regole.
# Fermare la pagina qui la renderebbe inutile proprio a inizio stagione,
# quando serve di piu'.
senza_partite = partite.empty
if senza_partite:
    st.info(
        "Le partite non sono ancora state importate: qui sotto trovi comunque "
        "la corrispondenza fra i weekend di Serie A e le giornate della lega.",
        icon="🗓️",
    )

squadre = (
    sorted(set(partite["casa"]) | set(partite["trasferta"])) if not senza_partite else []
)
disputate = ui.giornate_disputate(partite) if not senza_partite else 0
totale = int(partite["giornata"].max()) if not senza_partite else 0

ui.griglia_dati(
    [
        {"etichetta": "Squadre", "valore": str(len(squadre))},
        {
            "etichetta": "Giornate",
            "valore": f"{disputate}/{totale}",
            "nota": "disputate",
            "quota": disputate / max(totale, 1),
        },
        {
            "etichetta": "Partite",
            "valore": str(len(partite)),
            "nota": f"{int(partite['gol_casa'].notna().sum())} giocate",
        },
    ]
)

st.divider()

# Senza partite importate le altre schede non hanno niente da mostrare: non
# si creano proprio. Una scheda che si apre su un messaggio di scuse e' peggio
# di una scheda che non c'e'.
etichette = ["📆 Weekend"]
if not senza_partite:
    etichette += ["🗓️ Per giornata", "⚔️ Scontri diretti", "👤 Per squadra"]
schede = st.tabs(etichette)
weekend = schede[0]
per_giornata, griglia, per_squadra = (
    schede[1:] if not senza_partite else (nullcontext(), nullcontext(), nullcontext())
)


def riga_partita(riga) -> str:
    """Una partita in una riga sola, con il risultato se c'e'."""
    if pd.isna(riga.gol_casa):
        return f"**{riga.casa}** — **{riga.trasferta}**  ·  _da giocare_"
    return (
        f"**{riga.casa}** {int(riga.gol_casa)} – {int(riga.gol_trasferta)} "
        f"**{riga.trasferta}**  ·  {riga.punti_casa:.1f} – "
        f"{riga.punti_trasferta:.1f} punti"
    )


# --- 0. Weekend: Serie A contro fantacampionato -----------------------------

with weekend:
    st.markdown("**A cosa corrisponde questo weekend**")
    st.caption(
        "Le due numerazioni non coincidono: la lega parte a stagione gia' "
        "iniziata, e ogni turno di coppa fa slittare il campionato di una "
        "settimana. Qui si vede weekend per weekend cosa si gioca."
    )

    riga = st.columns(3)
    prima_serie_a = riga[0].number_input(
        "Il fantacampionato parte alla giornata di Serie A",
        min_value=1,
        max_value=38,
        value=5,
        step=1,
        help="La lega si forma dopo il draft di settembre.",
    )
    fino_a = riga[1].number_input(
        "Fino alla giornata di Serie A", min_value=2, max_value=38, value=38, step=1
    )
    riga[2].metric("Giornate di campionato", opzioni.giornate_totali)

    turni = costruisci_weekend(
        giornate_serie_a=int(fino_a),
        giornate_campionato=opzioni.giornate_totali,
        regole_coppa=opzioni.regole_coppa if opzioni.coppa_italia else None,
        prima_giornata_serie_a=int(prima_serie_a),
    )

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Weekend": indice,
                    "Serie A": f"{t.giornata_serie_a}ª giornata",
                    "Nella lega": t.descrizione,
                }
                for indice, t in enumerate(turni, start=1)
            ]
        ),
        hide_index=True,
        use_container_width=True,
        height=460,
    )

    if not opzioni.coppa_italia:
        st.caption(
            "La lega non gioca la Coppa Italia: campionato e Serie A restano "
            "allineati. Si attiva dalle impostazioni della lega."
        )


# --- 1. Per giornata --------------------------------------------------------

if not senza_partite:
    with per_giornata:
        scelta = st.slider(
            "Giornata", 1, totale, max(disputate, 1), help="Trascina per spostarti."
        )
        del_turno = partite[partite["giornata"] == scelta]
        giocata = del_turno["gol_casa"].notna().all()
        st.caption(f"Giornata {scelta} — {'disputata' if giocata else 'da giocare'}")
        for riga in del_turno.itertuples():
            st.markdown(riga_partita(riga))

        with st.expander("Vedi tutte le giornate in una tabella"):
            tabella = partite.copy()
            tabella["Risultato"] = [
                ""
                if pd.isna(r.gol_casa)
                else f"{int(r.gol_casa)} – {int(r.gol_trasferta)}"
                for r in partite.itertuples()
            ]
            st.dataframe(
                tabella[["giornata", "casa", "Risultato", "trasferta"]].rename(
                    columns={
                        "giornata": "G",
                        "casa": "Casa",
                        "trasferta": "Trasferta",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )


# --- 2. Scontri diretti -----------------------------------------------------


def griglia_incroci(partite: pd.DataFrame, squadre: list[str]) -> pd.DataFrame:
    """Matrice squadra x squadra: riga in casa, colonna in trasferta.

    Una cella vuota significa che quell'incrocio non e' in calendario — con un
    girone di sola andata meta' griglia resta vuota, ed e' corretto.
    """
    vuota = dict.fromkeys(squadre, "")
    celle = {casa: dict(vuota) for casa in squadre}
    for r in partite.itertuples():
        if pd.isna(r.gol_casa):
            celle[r.casa][r.trasferta] = f"G{int(r.giornata)}"
        else:
            celle[r.casa][r.trasferta] = f"{int(r.gol_casa)}–{int(r.gol_trasferta)}"
    for casa in squadre:
        celle[casa][casa] = "—"
    return pd.DataFrame(celle).T.reindex(index=squadre, columns=squadre)


if not senza_partite:
    with griglia:
        st.markdown("**Chi ha giocato contro chi**")
        st.caption(
            "Riga = squadra di casa, colonna = squadra in trasferta. Il numero e' "
            "il risultato; `G7` vuol dire che l'incrocio si gioca alla settima "
            "giornata; una cella vuota che quell'incrocio non e' in calendario."
        )
        st.dataframe(griglia_incroci(partite, squadre), use_container_width=True)

        st.divider()
        st.markdown("**Faccia a faccia**")
        coppia = st.columns(2)
        una = coppia[0].selectbox("Squadra", squadre, key="_h2h_a")
        altre = [s for s in squadre if s != una]
        due = coppia[1].selectbox("contro", altre, key="_h2h_b")

        incroci = partite[
            ((partite["casa"] == una) & (partite["trasferta"] == due))
            | ((partite["casa"] == due) & (partite["trasferta"] == una))
        ].sort_values("giornata")

        if incroci.empty:
            st.info(f"{una} e {due} non si incontrano in calendario.", icon="🤷")
        else:
            vinte_una = vinte_due = pari = 0
            for r in incroci.itertuples():
                st.markdown(f"Giornata {int(r.giornata)} · {riga_partita(r)}")
                if pd.isna(r.gol_casa):
                    continue
                if r.gol_casa == r.gol_trasferta:
                    pari += 1
                elif (r.gol_casa > r.gol_trasferta) == (r.casa == una):
                    vinte_una += 1
                else:
                    vinte_due += 1
            if vinte_una or vinte_due or pari:
                st.markdown(
                    " ".join(
                        [
                            tema.pastiglia(f"{una}: {vinte_una}", tema.VERDE),
                            tema.pastiglia(f"Pari: {pari}", tema.AMBRA),
                            tema.pastiglia(f"{due}: {vinte_due}", tema.AZZURRO),
                        ]
                    ),
                    unsafe_allow_html=True,
                )


# --- 3. Per squadra ---------------------------------------------------------

if not senza_partite:
    with per_squadra:
        scelta_squadra = st.selectbox("Squadra", squadre, key="_cal_squadra")
        sue = partite[
            (partite["casa"] == scelta_squadra) | (partite["trasferta"] == scelta_squadra)
        ].sort_values("giornata")

        righe = []
        for r in sue.itertuples():
            in_casa = r.casa == scelta_squadra
            avversaria = r.trasferta if in_casa else r.casa
            if pd.isna(r.gol_casa):
                esito, risultato = "", ""
            else:
                miei = int(r.gol_casa if in_casa else r.gol_trasferta)
                suoi = int(r.gol_trasferta if in_casa else r.gol_casa)
                risultato = f"{miei} – {suoi}"
                esito = "Vinta" if miei > suoi else "Persa" if miei < suoi else "Pari"
            righe.append(
                {
                    "G": int(r.giornata),
                    "Dove": "Casa" if in_casa else "Trasferta",
                    "Avversaria": avversaria,
                    "Risultato": risultato,
                    "Esito": esito,
                }
            )

        tabella = pd.DataFrame(righe)
        st.dataframe(tabella, hide_index=True, use_container_width=True)

        giocate = tabella[tabella["Esito"] != ""]
        if not giocate.empty:
            conteggi = giocate["Esito"].value_counts()
            st.markdown(
                " ".join(
                    [
                        tema.pastiglia(f"Vinte: {conteggi.get('Vinta', 0)}", tema.VERDE),
                        tema.pastiglia(f"Pari: {conteggi.get('Pari', 0)}", tema.AMBRA),
                        tema.pastiglia(f"Perse: {conteggi.get('Persa', 0)}", tema.ROSSO),
                    ]
                ),
                unsafe_allow_html=True,
            )
