"""Importazione da CSV: l'esito del draft e i risultati di giornata.

Il flusso e' sempre lo stesso: carichi il file, guardi l'anteprima con gli
errori riga per riga, e solo dopo confermi la scrittura.
"""

import pandas as pd
import streamlit as st

from fantacalcio import ui, vista
from fantacalcio.data import archivio
from fantacalcio.importazione import (
    anteprima_conformita,
    applica_listone,
    applica_risultati,
    applica_rose,
    catalogo_giocatori,
    importa_listone,
    importa_risultati,
    importa_rose,
    modello_risultati,
    modello_rose,
)

ui.intestazione(
    "Importa dati",
    "📥",
    "Il draft si fa di persona: qui si carica il CSV con il risultato.",
)
ui.barra_laterale()


def tabella_problemi(problemi) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Riga": p.riga,
                "Colonna": p.colonna,
                "Valore": p.valore,
                "Problema": p.messaggio,
            }
            for p in problemi
        ]
    )


listone, rose, risultati = st.tabs(
    ["Listone giocatori", "Rose dal draft", "Risultati di giornata"]
)

with listone:
    st.markdown(
        "Il **listone ufficiale** di Fantacalcio.it (`Quotazioni_Fantacalcio_"
        "Stagione_*.xlsx`): anagrafica, ruoli Mantra, squadra di Serie A e "
        "quotazioni di tutti i giocatori."
    )
    st.info(
        "Il listone **non contiene** le assegnazioni alle squadre della lega, "
        "gli anni di contratto ne' gli ingaggi Capology: serve a popolare il "
        "catalogo. Caricato questo, il file delle rose puo' limitarsi a "
        "`squadra`, `giocatore`, `anni`, `ingaggio`.",
        icon="ℹ️",
    )

    file_listone = st.file_uploader("Listone (.xlsx)", type=["xlsx"], key="xlsx_listone")
    if file_listone is None:
        st.info("Carica il file per vedere l'anteprima.", icon="👆")
    else:
        esito_listone = importa_listone(file_listone.getvalue())

        colonne = st.columns(2)
        colonne[0].metric("Giocatori letti", len(esito_listone.righe))
        colonne[1].metric("Errori", len(esito_listone.errori))

        if esito_listone.errori:
            st.error("Correggi gli errori prima di importare.", icon="⛔")
            st.dataframe(
                tabella_problemi(esito_listone.errori),
                hide_index=True,
                use_container_width=True,
            )

        if esito_listone.righe:
            anteprima_listone = pd.DataFrame(
                [
                    {
                        "Id": r["id_ufficiale"],
                        "Giocatore": r["nome"],
                        "Club": r["club"],
                        "Ruoli": "/".join(r["ruoli"]),
                        "Quotazione": r["quotazione"],
                        "Valore di mercato": r["fvm"],
                    }
                    for r in esito_listone.righe
                ]
            )
            st.dataframe(
                anteprima_listone,
                hide_index=True,
                use_container_width=True,
                height=320,
            )
            st.caption(
                f"{anteprima_listone['Club'].nunique()} squadre di Serie A. "
                "I giocatori gia' presenti mantengono ingaggio e contratto: il "
                "listone aggiorna solo ruoli, club e quotazioni."
            )

        if st.button(
            "Importa il listone",
            type="primary",
            disabled=not esito_listone.importabile,
        ):
            riepilogo = applica_listone(archivio(), esito_listone)
            ui.invalida_dati()
            st.success(
                f"{riepilogo['totali']} giocatori nel catalogo "
                f"({riepilogo['nuovi']} nuovi, {riepilogo['aggiornati']} aggiornati).",
                icon="✅",
            )

with rose:
    st.markdown(
        "Una riga per giocatore. Le intestazioni sono riconosciute anche se "
        "scritte diversamente (`Fantasquadra`, `Calciatore`, `Stipendio`, "
        "`Durata`...), il separatore puo' essere `;` o `,`, e gli importi si "
        "possono scrivere all'italiana: `3.500.000`, `3,5M`, `€ 2.100.000`."
    )
    st.download_button(
        "Scarica il modello CSV",
        data=modello_rose(),
        file_name="modello_rose_fantacalcio_nuovo.csv",
        mime="text/csv",
    )

    file_rose = st.file_uploader("CSV delle rose", type=["csv", "txt"], key="csv_rose")
    if file_rose is None:
        st.info("Carica il CSV per vedere l'anteprima.", icon="👆")
    else:
        catalogo = catalogo_giocatori(archivio())
        if catalogo:
            st.caption(
                f"Listone caricato ({len(catalogo)} giocatori): puoi omettere "
                f"`ruoli` e `club`, si ricavano dal nome."
            )
        esito = importa_rose(file_rose.getvalue(), ui.parametri(), catalogo or None)

        colonne = st.columns(3)
        colonne[0].metric("Righe lette", len(esito.righe))
        colonne[1].metric("Errori", len(esito.errori))
        colonne[2].metric("Avvisi", len(esito.avvisi))

        if esito.intestazioni_ignorate:
            st.caption(
                "Colonne ignorate perche' non riconosciute: "
                + ", ".join(esito.intestazioni_ignorate)
            )

        if esito.errori:
            st.error(
                f"{len(esito.errori)} errori da correggere prima di importare.",
                icon="⛔",
            )
            st.dataframe(
                tabella_problemi(esito.errori),
                hide_index=True,
                use_container_width=True,
            )

        if esito.avvisi:
            with st.expander(f"Avvisi ({len(esito.avvisi)})"):
                st.dataframe(
                    tabella_problemi(esito.avvisi),
                    hide_index=True,
                    use_container_width=True,
                )

        if esito.righe:
            st.subheader("Anteprima delle rose")
            anteprima = pd.DataFrame(
                [
                    {
                        "Squadra": r["squadra"],
                        "Giocatore": r["giocatore"],
                        "Club": r["club"],
                        "Ruoli": "/".join(r["ruoli"]),
                        "Anni": r["anni"],
                        "Ingaggio": r["ingaggio"],
                    }
                    for r in esito.righe
                ]
            )
            st.dataframe(
                ui.in_milioni(anteprima),
                hide_index=True,
                use_container_width=True,
                column_config=ui.COLONNE_EURO,
                height=300,
            )

            st.subheader("Le rose sarebbero conformi al regolamento?")
            st.caption(
                "Verifica fatta prima di scrivere: se il draft ha lasciato "
                "qualcuno fuori dai paletti, si vede adesso."
            )
            stati = anteprima_conformita(esito, ui.DATA_DRAFT, ui.parametri())
            st.dataframe(
                ui.in_milioni(vista.cruscotto_lega(stati)),
                hide_index=True,
                use_container_width=True,
                column_config=ui.COLONNE_EURO,
            )
            violazioni = vista.violazioni_lega(stati)
            if not violazioni.empty:
                st.warning(
                    f"{len(violazioni)} violazioni: puoi importare comunque, ma "
                    f"vanno sanate prima della chiusura del mercato.",
                    icon="⚠️",
                )
                st.dataframe(violazioni, hide_index=True, use_container_width=True)

        st.divider()
        sostituisci = st.checkbox(
            "Sostituisci le rose esistenti",
            value=True,
            help=(
                "Dopo un draft il CSV rappresenta la situazione completa: le "
                "rose precedenti vengono azzerate. Le squadre mantengono "
                "identita' e colori."
            ),
        )
        if st.button(
            "Importa le rose",
            type="primary",
            disabled=not esito.importabile,
        ):
            riepilogo = applica_rose(archivio(), esito, sostituisci=sostituisci)
            ui.invalida_dati()
            st.success(
                f"Importati {riepilogo['giocatori']} giocatori e "
                f"{riepilogo['contratti']} contratti. "
                f"Squadre create: {riepilogo['squadre_create']}.",
                icon="✅",
            )

with risultati:
    st.markdown(
        "Una riga per partita, con i punti fantacalcio di ciascuna squadra. "
        "I gol vengono calcolati dalle fasce della lega (primo gol a "
        f"{ui.parametri().soglia_primo_gol:.0f}, poi uno ogni "
        f"{ui.parametri().passo_gol:.0f})."
    )
    st.download_button(
        "Scarica il modello CSV",
        data=modello_risultati(),
        file_name="modello_risultati_fantacalcio_nuovo.csv",
        mime="text/csv",
        key="modello_risultati",
    )

    file_risultati = st.file_uploader(
        "CSV dei risultati", type=["csv", "txt"], key="csv_risultati"
    )
    if file_risultati is None:
        st.info("Carica il CSV per vedere l'anteprima.", icon="👆")
    else:
        esito = importa_risultati(file_risultati.getvalue())

        colonne = st.columns(2)
        colonne[0].metric("Partite lette", len(esito.righe))
        colonne[1].metric("Errori", len(esito.errori))

        if esito.errori:
            st.error("Correggi gli errori prima di importare.", icon="⛔")
            st.dataframe(
                tabella_problemi(esito.errori),
                hide_index=True,
                use_container_width=True,
            )

        if esito.righe:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Giornata": r["giornata"],
                            "Casa": r["casa"],
                            "Trasferta": r["trasferta"],
                            "Punti casa": r["punti_casa"],
                            "Punti trasferta": r["punti_trasferta"],
                        }
                        for r in esito.righe
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )

        if st.button(
            "Importa i risultati", type="primary", disabled=not esito.importabile
        ):
            try:
                riepilogo = applica_risultati(archivio(), esito)
            except ValueError as errore:
                st.error(str(errore), icon="⛔")
            else:
                ui.invalida_dati()
                st.success(f"Importate {riepilogo['partite']} partite.", icon="✅")
