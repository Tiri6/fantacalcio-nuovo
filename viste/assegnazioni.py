"""Assegnazioni del draft: giocatore per giocatore, o in blocco da CSV.

Il draft si conduce fuori dalla piattaforma. Qui si registra il risultato:
o si assegna un giocatore alla volta durante l'asta, o si carica il file
quando e' finita.
"""

import pandas as pd
import streamlit as st

from fantacalcio import schermate, tema, ui
from fantacalcio.data import archivio
from fantacalcio.importazione import importa_rose

ui.barra_laterale()
schermate.mostra_messaggio()

utente = ui.utente_corrente()
lega = ui.lega_corrente()
opzioni = lega.opzioni

ui.intestazione(
    "Assegnazioni",
    "📝",
    "Registra chi si e' preso chi: uno alla volta durante l'asta, o tutti "
    "insieme quando e' finita.",
)

if not utente.puo_importare:
    st.warning("Le assegnazioni le registra il presidente di lega (art. 1).", icon="🔒")
    st.stop()

giocatori = ui.giocatori_con_proprietario()
if giocatori.empty:
    st.info(
        "Il listone non e' ancora caricato: senza, non c'e' niente da "
        "assegnare. Si importa dalla pagina «Importa dati».",
        icon="📋",
    )
    st.stop()

rose = ui.rose()
nomi_squadre = sorted(r.squadra.nome for r in rose.values())
per_nome = {r.squadra.nome: r for r in rose.values()}

svincolati = giocatori[giocatori["Squadra"] == ui.SVINCOLATO]

ui.griglia_dati(
    [
        {"etichetta": "Squadre", "valore": str(len(nomi_squadre))},
        {
            "etichetta": "Da assegnare",
            "valore": str(len(svincolati)),
            "nota": f"su {len(giocatori)} in listone",
            "quota": 1 - len(svincolati) / max(len(giocatori), 1),
        },
        {
            "etichetta": "Anni disponibili",
            "valore": f"1–{opzioni.anni_contratto_massimi}",
            "nota": "per contratto",
        },
    ]
)

st.divider()

uno, blocco = st.tabs(["🎯 Un giocatore alla volta", "📥 Carica un CSV"])


# --- uno alla volta ---------------------------------------------------------

with uno:
    if not nomi_squadre:
        st.warning("Nessuna squadra iscritta.", icon="🫥")
    elif svincolati.empty:
        st.success("Tutti i giocatori del listone sono assegnati.", icon="✅")
    else:
        riga = st.columns([3, 2, 1])
        cerca = riga[0].text_input(
            "Giocatore", placeholder="Scrivi qualche lettera del nome"
        )
        candidati = svincolati
        if cerca.strip():
            testo = cerca.strip().lower()
            candidati = candidati[
                candidati["Giocatore"].str.lower().str.contains(testo, na=False)
            ]

        if candidati.empty:
            st.caption("Nessuno svincolato con questo nome.")
        else:
            etichette = {
                f"{r.Giocatore} ({r.Club}, {r.Ruoli})": r.Index
                for r in candidati.head(50).itertuples()
            }
            scelto = riga[1].selectbox("Scegli", list(etichette))
            anni = riga[2].number_input(
                "Anni", 1, opzioni.anni_contratto_massimi, 1, key="_assegna_anni"
            )

            riga = st.columns([2, 2])
            squadra = riga[0].selectbox("Alla squadra", nomi_squadre)
            dettaglio = candidati.loc[etichette[scelto]]
            riga[1].markdown(
                f"**Ingaggio**  \n{dettaglio['Ingaggio'] / 1_000_000:.2f}M  ·  "
                f"**{dettaglio['Nazionalita']}**"
                + ("  ·  🇮🇹 U21" if dettaglio["U21"] else "")
            )

            rosa = per_nome[squadra]
            residuo = opzioni.budget_cap - rosa.monte_ingaggi - dettaglio["Ingaggio"]
            anni_dopo = rosa.anni_impegnati + int(anni)
            monte = ui.parametri().monte_anni

            avvisi = []
            if residuo < 0:
                avvisi.append(f"Sfora il budget cap di {abs(residuo) / 1_000_000:.2f}M")
            if anni_dopo > monte:
                avvisi.append(
                    f"Porta il monte anni a {anni_dopo}, oltre il tetto di {monte}"
                )
            for avviso in avvisi:
                st.warning(avviso, icon="⚠️")

            if st.button(
                f"Assegna a {squadra}", type="primary", use_container_width=True
            ):
                testo_csv = (
                    "squadra;giocatore;club;ruoli;ingaggio;anni\n"
                    f"{squadra};{dettaglio['Giocatore']};{dettaglio['Club']};"
                    f"{dettaglio['Ruoli']};{dettaglio['Ingaggio']};{int(anni)}\n"
                )
                esito = importa_rose(testo_csv, ui.parametri(), catalogo=True)
                if esito.problemi:
                    for problema in esito.problemi:
                        st.error(problema.messaggio, icon="⛔")
                else:
                    from fantacalcio.importazione import applica_rose

                    try:
                        applica_rose(archivio(), esito, sostituisci=False)
                    except Exception as errore:  # noqa: BLE001 - backend diversi
                        st.error(f"Non riesco a salvare: {errore}", icon="⛔")
                    else:
                        ui.invalida_dati()
                        st.session_state[schermate.CHIAVE_MESSAGGIO] = (
                            "success",
                            f"{dettaglio['Giocatore']} a {squadra}, "
                            f"{int(anni)} "
                            + ("anno" if int(anni) == 1 else "anni")
                            + ".",
                        )
                        st.rerun()


# --- in blocco --------------------------------------------------------------

with blocco:
    st.markdown("**Il formato del file**")
    st.caption(
        "Una riga per giocatore. Le colonne si riconoscono dal nome, in "
        "qualsiasi ordine; `costo` vale come anni di contratto."
    )
    modello = pd.DataFrame(
        [
            {
                "squadra": "Tiri Team",
                "id_giocatore": 2071,
                "giocatore": "Dybala",
                "anni": 3,
                "ingaggio": 4_500_000,
            },
            {
                "squadra": "Padel United",
                "id_giocatore": 486,
                "giocatore": "Lautaro Martinez",
                "anni": 5,
                "ingaggio": 6_000_000,
            },
        ]
    )
    st.dataframe(modello, hide_index=True, use_container_width=True)
    st.download_button(
        "Scarica il modello CSV",
        modello.to_csv(index=False, sep=";").encode("utf-8"),
        file_name="assegnazioni-draft.csv",
        mime="text/csv",
    )

    st.markdown(
        tema.scheda(
            "Da dove arrivano gli stipendi",
            "Dalla fonte ufficiale della lega, Capology (art. 4). L'id "
            "giocatore e' quello del listone: aggancia la riga anche se il "
            "nome e' scritto diversamente.",
            icona="💶",
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        "Il caricamento vero, con anteprima e controllo riga per riga, sta "
        "nella pagina «Importa dati»: e' lo stesso lettore, con la verifica "
        "di conformita' prima di scrivere."
    )
